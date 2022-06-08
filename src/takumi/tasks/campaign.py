import datetime as dt

from sqlalchemy import or_

from takumi.events.campaign import CampaignLog
from takumi.extensions import db, tiger
from takumi.models import Campaign, CampaignMetric, Device, Influencer, Notification, Offer, User
from takumi.services import CampaignService, OfferService


@tiger.task(unique=True)
def create_or_update_campaign_metric(campaign_id):
    """A task that creates or updates a campaign to campaign metrics by id.
    All properties are called here in advance to shorten the request time.

    Args:
        campaign_id (UUID): The campaign's id.

    Note:
        Only campaigns that have the launched status are updated.
    """
    campaign = Campaign.query.get(campaign_id)

    if campaign_metric := campaign.campaign_metric:
        if campaign.state == Campaign.STATES.LAUNCHED:
            campaign_metric.engagement_rate_total = campaign.engagement_rate_total
            campaign_metric.engagement_rate_static = campaign.engagement_rate_static
            campaign_metric.engagement_rate_story = campaign.engagement_rate_story
            campaign_metric.impressions_total = campaign.impressions_total
            campaign_metric.reach_total = campaign.reach_total
            campaign_metric.assets = campaign.units
    else:
        new_campaign_metric = CampaignMetric(
            campaign_id=campaign_id,
            engagement_rate_total=campaign.engagement_rate_total,
            engagement_rate_static=campaign.engagement_rate_static,
            engagement_rate_story=campaign.engagement_rate_story,
            impressions_total=campaign.impressions_total,
            reach_total=campaign.reach_total,
            assets=campaign.units,
        )
        db.session.add(new_campaign_metric)

    db.session.commit()


@tiger.task(unique=True, lock=True, lock_key="notify_all_targeted")
def notify_all_targeted(campaign_id, not_notified_in_the_last_hours=None):
    campaign = Campaign.query.get(campaign_id)
    if not campaign.public:
        return

    if not_notified_in_the_last_hours:
        now = dt.datetime.now(dt.timezone.utc)
        min_last_notification_date = now - dt.timedelta(hours=not_notified_in_the_last_hours)

    has_notifications = (
        Notification.query.filter(Notification.campaign_id == campaign.id).count() > 0
    )

    devices = (
        Device.query.join(User)
        .join(Influencer)
        .filter(Influencer.matches_campaign(campaign))
        .filter(
            or_(
                Influencer.last_notification_sent(campaign) == None,
                (Influencer.last_notification_sent(campaign) < min_last_notification_date)
                if not_notified_in_the_last_hours
                else False,
            )
            if has_notifications
            else True
        )
        .all()
    )

    with CampaignService(campaign) as srv:
        srv.notify_devices(devices)


@tiger.task(unique=True)
def force_stash(campaign_id: str) -> None:
    campaign = Campaign.query.get(campaign_id)
    if campaign.state == Campaign.STATES.DRAFT:
        # Just stash it normally
        with CampaignService(campaign) as camp_service:
            camp_service.stash()
    elif campaign.state == Campaign.STATES.LAUNCHED:
        offer: Offer
        for offer in campaign.offers:
            if offer.state in (
                Offer.STATES.PENDING,
                Offer.STATES.INVITED,
                Offer.STATES.ACCEPTED,
                Offer.STATES.REQUESTED,
                Offer.STATES.APPROVED_BY_BRAND,
                Offer.STATES.CANDIDATE,
            ):
                with OfferService(offer) as offer_service:
                    offer_service.revoke()

        # Verify all offers are rejected, revoked or rejected by brand
        for offer in campaign.offers:
            if offer.state not in (
                Offer.STATES.REJECTED,
                Offer.STATES.REVOKED,
                Offer.STATES.REJECTED_BY_BRAND,
            ):
                raise Exception(f"Offer ({offer.id}) not revoked/rejected (actually {offer.state})")
    else:
        raise Exception("Campaign can't be stashed if not draft/launched")

    log = CampaignLog(campaign)
    log.add_event("stash")
    db.session.commit()
