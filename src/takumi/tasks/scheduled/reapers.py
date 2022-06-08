import datetime as dt
import random

from sentry_sdk import capture_exception
from sqlalchemy import func
from tasktiger.schedule import periodic

from takumi.emails import (
    CandidatesReadyForReviewEmail,
    EndOfCampaignEmail,
    GigReadyForApprovalEmail,
    NewCommentEmail,
)
from takumi.extensions import db, tiger
from takumi.models import (
    Campaign,
    Comment,
    Gig,
    Influencer,
    Offer,
    Post,
    User,
    UserCommentAssociation,
)
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.user import EMAIL_NOTIFICATION_PREFERENCES
from takumi.services import CampaignService, OfferService

MAX_STAGGER_STEP = 60  # seconds


# TODO: Solve this in a cleaner way
def _story_campaigns_quickfix():
    # Quickfix for when the last gig submitted event wasn't triggered
    campaign_subq = (
        db.session.query(Post.campaign_id)
        .join(Campaign)
        .filter(Campaign.state == CAMPAIGN_STATES.LAUNCHED, ~Campaign.pro_bono)
        .subquery()
    )
    offers = [
        o
        for o in Offer.query.filter(
            Offer.payable == None,
            Offer.is_claimable == False,
            Offer.state == "accepted",
            Offer.campaign_id.in_(campaign_subq),
        ).all()
        if o.has_all_gigs_claimable()
    ]
    for offer in offers:
        with OfferService(offer) as service:
            service.last_gig_submitted()


def _set_payable_date_if_missing() -> None:
    post_count_subq = (
        db.session.query(
            Post.campaign_id.label("campaign_id"), func.count(Post.id).label("post_count")
        )
        .group_by(Post.campaign_id)
        .subquery()
    )

    gig_count_subq = (
        db.session.query(
            Gig.offer_id.label("offer_id"), func.count(Gig.offer_id).label("gig_count")
        )
        .filter(Gig.is_live)
        .group_by(Gig.offer_id)
        .subquery()
    )

    q = (
        Offer.query.join(Campaign)
        .join(post_count_subq, post_count_subq.c.campaign_id == Campaign.id)
        .join(gig_count_subq, gig_count_subq.c.offer_id == Offer.id)
        .filter(
            ~Campaign.pro_bono,
            ~Offer.is_claimable,
            post_count_subq.c.post_count == gig_count_subq.c.gig_count,
            Offer.payable == None,
            Offer.state == Offer.STATES.ACCEPTED,
        )
    )

    offer: Offer
    for offer in q:
        with OfferService(offer) as s:
            s.last_gig_submitted()


@tiger.scheduled(periodic(hours=1))
def offer_claimability_reaper():
    """Find offers which should have become claimable by now, but haven't.

    This can happen for a couple of reasons, including:

    1. When an offer should have become claimable, one or more of it's gigs
    were reported, and thus the offer should not be claimable.  Later the
    report is dismissed, but no new callback issued.
    2. The callback failed for some reason
    """

    _story_campaigns_quickfix()
    _set_payable_date_if_missing()

    now = dt.datetime.now(dt.timezone.utc)
    offers = Offer.query.filter(
        Offer.payable <= now, Offer.is_claimable == False, Offer.state == OFFER_STATES.ACCEPTED
    )

    def get_callback_delay(gig: Gig) -> float:
        """Returns when to schedule the claimability callback check based on the
        claimable_time timestamp for the given gig.

        Returns the "right" time if it's in the future, otherwise a random delay
        between 1 and 60 seconds to spread the callbacks over a period of one minute
        if a lot of offers are affected at the same time.
        """
        if gig.claimable_time is None:
            raise Exception("Gig doesn't have claimable time")

        return max(
            (gig.claimable_time - dt.datetime.now(dt.timezone.utc)).total_seconds() + 5,
            random.randint(1, 60),
        )

    def fix_payable_date(offer: Offer, gig: Gig) -> None:
        if offer.payable != gig.claimable_time:
            offer.payable = gig.claimable_time
            db.session.add(offer)
            db.session.commit()

    for offer in offers:
        try:
            if offer.has_all_gigs_claimable():
                last_gig = sorted(
                    [gig for gig in offer.gigs if gig.is_valid],
                    key=lambda gig: gig.claimable_time,
                    reverse=True,
                )[0]
                with OfferService(offer) as service:
                    service.set_claimable()
                fix_payable_date(offer, last_gig)
                complete_campaign(offer.campaign)
        except Exception:
            capture_exception(exc_info=None, data={"offer_id": offer.id})


def complete_campaign(campaign):
    if not campaign.is_fulfilled:
        return

    if not campaign.all_claimable:
        return

    from takumi.services import CampaignService
    from takumi.services.exceptions import CampaignCompleteException

    with CampaignService(campaign) as service:
        try:
            service.complete()
        except CampaignCompleteException:
            return

    EndOfCampaignEmail(
        {"advertiser_domain": campaign.advertiser.domain, "campaign_id": campaign.id}
    ).send_many([user.email for user in campaign.advertiser.users])


def _notify_clients_that_have_gigs_ready_for_approval(
    time_period_ago, email_notification_preference
):
    campaigns = CampaignService.get_campaigns_with_gigs_ready_for_approval(time_period_ago)
    for campaign in campaigns:
        advertiser = campaign.advertiser
        non_takumi_addresses = [
            user.email
            for user in advertiser.users
            if not user.email.endswith("@takumi.com")
            and user.email_notification_preference == email_notification_preference
        ]
        GigReadyForApprovalEmail(
            {
                "advertiser_domain": advertiser.domain,
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
            }
        ).send_many(non_takumi_addresses)


def _notify_clients_that_have_candidates_ready_for_approval(
    time_period_ago, email_notification_preference
):
    campaigns_waiting_for_candidate_review = (
        CampaignService.get_campaigns_with_candidates_ready_for_review(time_period_ago)
    )
    for campaign in campaigns_waiting_for_candidate_review:
        advertiser = campaign.advertiser
        non_takumi_addresses = [
            user.email
            for user in advertiser.users
            if not user.email.endswith("@takumi.com")
            and user.email_notification_preference == email_notification_preference
        ]
        CandidatesReadyForReviewEmail(
            {
                "advertiser_domain": advertiser.domain,
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
            }
        ).send_many(non_takumi_addresses)


def _notify_clients_that_have_unseen_comments(time_period_ago, email_notification_preference):
    email_list = {}

    campaigns_with_new_comments = (
        Campaign.query.join(Offer, Offer.campaign_id == Campaign.id)
        .join(Influencer)
        .join(User)
        .filter(Offer.comments.any(Comment.created > time_period_ago))
        .distinct(User.id)
        .all()
    )
    for campaign in campaigns_with_new_comments:
        new_campaign_comments = Comment.query.filter(
            Comment.owner_type == "offer",
            Comment.owner_id.in_(
                Offer.query.filter(Offer.campaign_id == campaign.id).with_entities(Offer.id)
            ),
            Comment.created > time_period_ago,
        ).with_entities(Comment.id)
        for user in campaign.advertiser.users:
            if user.email.endswith("@takumi.com"):
                # skip takumis
                continue

            seen_comments_count = UserCommentAssociation.query.filter(
                UserCommentAssociation.user_id == user.id,
                UserCommentAssociation.comment_id.in_(new_campaign_comments),
            ).count()

            if (
                seen_comments_count < new_campaign_comments.count()
                and user.email_notification_preference == email_notification_preference
            ):
                if user.email in email_list:
                    email_list[user.email].append(campaign)
                else:
                    email_list[user.email] = [campaign]

    for email, campaigns in email_list.items():
        NewCommentEmail({"campaigns": campaigns}).send(email)


@tiger.scheduled(periodic(days=1))
def client_notifications_daily_reaper():
    time_period_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    _notify_clients_that_have_gigs_ready_for_approval(
        time_period_ago, EMAIL_NOTIFICATION_PREFERENCES.DAILY
    )
    _notify_clients_that_have_candidates_ready_for_approval(
        time_period_ago, EMAIL_NOTIFICATION_PREFERENCES.DAILY
    )
    _notify_clients_that_have_unseen_comments(time_period_ago, EMAIL_NOTIFICATION_PREFERENCES.DAILY)


@tiger.scheduled(periodic(hours=1))
def client_notifications_hourly_reaper():
    time_period_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    _notify_clients_that_have_gigs_ready_for_approval(
        time_period_ago, EMAIL_NOTIFICATION_PREFERENCES.HOURLY
    )
    _notify_clients_that_have_candidates_ready_for_approval(
        time_period_ago, EMAIL_NOTIFICATION_PREFERENCES.HOURLY
    )
    _notify_clients_that_have_unseen_comments(
        time_period_ago, EMAIL_NOTIFICATION_PREFERENCES.HOURLY
    )
