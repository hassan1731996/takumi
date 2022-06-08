import datetime as dt
import json
from itertools import groupby
from typing import List

from sqlalchemy import and_, func

from takumi.events.campaign import CampaignLog
from takumi.extensions import db
from takumi.i18n import gettext as _
from takumi.i18n import locale_context
from takumi.models import (
    Campaign,
    CampaignMetric,
    Gig,
    Influencer,
    Insight,
    Notification,
    Offer,
    Post,
)
from takumi.models.campaign import STATES
from takumi.models.device import Device
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.insight import STATES as INSIGHT_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.user import User
from takumi.notifications import NotificationClient
from takumi.services import Service
from takumi.services.exceptions import (
    CampaignCompleteException,
    CampaignLaunchException,
    CampaignPreviewException,
    CampaignPromotionException,
    CampaignStashException,
    InfluencerNotFound,
    InvalidCampaignStateException,
    InvalidOfferIdException,
    InvalidPromptsException,
    NegativePriceException,
    OrderHasUpdatedException,
    ServiceException,
)
from takumi.services.validation import Validate
from takumi.signers import url_signer
from takumi.utils import uuid4_str

from .schemas import CompleteSchema, LaunchSchema, StashSchema


def _clean_and_validate_prompts(prompts):  # noqa
    prompts = json.loads(json.dumps(prompts))
    n_confirmations = 0
    for prompt in prompts:
        choices = prompt.get("choices")
        if prompt["type"] == "confirm":
            prompt["text"] = "Confirmation"
            n_confirmations += 1
            if n_confirmations > 1:
                prompt["text"] = prompt["text"] + f" {n_confirmations}"
        if choices is not None:
            prompt["choices"] = [c.strip() for c in choices if c.strip()]
            if prompt["choices"] == []:
                if prompt["type"] in ["multiple_choice", "single_choice"]:
                    raise InvalidPromptsException("Prompt must have at least 1 choice")
                if prompt["type"] == "confirm":
                    raise InvalidPromptsException(
                        "Confirm screens must have at least 1 confirmations"
                    )
                del prompt["choices"]
        if prompt.get("text") is not None:
            prompt["text"] = prompt["text"].strip()
            if prompt["text"] == "":
                if prompt["type"] != "confirm":
                    raise InvalidPromptsException("Prompt must have a text")
                del prompt["text"]
    return prompts


class CampaignService(Service):
    """
    Represents the business model for Campaign. This isolates the database
    from the application.
    """

    SUBJECT = Campaign
    LOG = CampaignLog

    @property
    def campaign(self):
        return self.subject

    # GET
    @staticmethod
    def get_by_id(id):
        return Campaign.query.get(id)

    @staticmethod
    def get_by_report_token(report_token):
        return Campaign.query.filter(Campaign.report_token == report_token).one_or_none()

    @staticmethod
    def get_insights_count(id):
        return (
            Insight.query.join(Gig)
            .join(Post)
            .filter(
                Post.campaign_id == id,
                Insight.state.in_([INSIGHT_STATES.SUBMITTED, INSIGHT_STATES.APPROVED]),
            )
            .count()
        )

    @staticmethod
    def get_submissions_count(id):
        return (
            Gig.query.join(Offer)
            .join(Campaign)
            .filter(
                Campaign.id == id,
                Gig.state.in_(
                    [
                        GIG_STATES.SUBMITTED,
                        GIG_STATES.REVIEWED,
                        GIG_STATES.APPROVED,
                        GIG_STATES.REJECTED,
                    ]
                ),
                Offer.state == OFFER_STATES.ACCEPTED,
            )
            .count()
        )

    @staticmethod
    def get_active_campaigns():
        return db.session.query(Campaign.id).filter(Campaign.is_active).all()

    @staticmethod
    def get_campaigns_with_gigs_ready_for_approval(
        time_period_ago=dt.datetime.min.replace(tzinfo=dt.timezone.utc),
    ):
        query = (
            Campaign.query.join(Post)
            .join(Gig)
            .filter(
                Campaign.brand_safety,
                Campaign.posts.any(
                    Post.gigs.any(
                        and_(Gig.state == GIG_STATES.REVIEWED, Gig.review_date > time_period_ago)
                    )
                ),
            )
            .distinct(Campaign.id)
        )

        return query.all()

    @staticmethod
    def get_campaigns_with_candidates_ready_for_review(
        time_period_ago=dt.datetime.min.replace(tzinfo=dt.timezone.utc),
    ):
        query = (
            Campaign.query.join(Offer)
            .filter(
                Campaign.brand_safety,
                Campaign.offers.any(Offer.state == OFFER_STATES.CANDIDATE),
                Campaign.is_active,
                Campaign.candidates_submitted > time_period_ago,
            )
            .distinct(Campaign.id)
        )

        return query.all()

    @staticmethod
    def get_participation(id):
        return (
            Offer.query.filter(Offer.campaign_id == id)
            .with_entities(func.count(Offer.id).label("count"), Offer.state)
            .group_by(Offer.state)
            .all()
        )

    @staticmethod
    def get_number_of_accepted_influencers(campaign_ids: List[str]) -> int:
        return (
            Offer.query.filter(
                Offer.campaign_id.in_(campaign_ids), Offer.state == OFFER_STATES.ACCEPTED
            )
            .with_entities(Offer.influencer_id)
            .count()
            or 0
        )

    @staticmethod
    def get_campaigns_impressions(campaign_ids: List[str]) -> int:
        """How many times the content was shown to the audience
        as the sum of all impressions of posts within specific campaigns.

        Args:
            campaign_ids: List of campaigns' ids.

        Returns:
            Total filtered impressions, where the campaign is in the passed ids list.
        """
        return (
            db.session.query(func.sum(CampaignMetric.impressions_total))
            .filter(Campaign.id.in_(campaign_ids), CampaignMetric.campaign_id == Campaign.id)
            .scalar()
            or 0
        )

    # POST
    @staticmethod
    def create_campaign(
        *,
        advertiser_id,
        market,
        reward_model,
        units,
        shipping_required,
        require_insights,
        price,
        list_price,
        custom_reward_units,
        name,
        description,
        pictures,
        owner_id,
        prompts,
        campaign_manager_id,
        secondary_campaign_manager_id,
        community_manager_id,
        tags,
        has_nda,
        brand_safety,
        brand_match,
        extended_review,
        industry,
        opportunity_product_id,
        pro_bono,
    ):
        if tags is None:
            tags = []

        campaign = Campaign()
        log = CampaignLog(campaign)
        log.add_event(
            "create",
            {
                "market_slug": market.slug,
                "reward_model": reward_model,
                "units": units,
                "price": price,
                "list_price": list_price,
                "shipping_required": shipping_required,
                "require_insights": require_insights,
                "custom_reward_units": custom_reward_units,
                "name": name,
                "description": description,
                "pictures": pictures,
                "owner_id": owner_id,
                "prompts": _clean_and_validate_prompts(prompts),
                "campaign_manager_id": campaign_manager_id,
                "secondary_campaign_manager_id": secondary_campaign_manager_id,
                "community_manager_id": community_manager_id,
                "tags": [t.lower() for t in tags],
                "has_nda": has_nda,
                "brand_safety": brand_safety,
                "brand_match": brand_match,
                "apply_first": True,
                "extended_review": extended_review,
                "industry": industry,
                "advertiser_id": advertiser_id,
                "timezone": market.default_timezone,
                "opportunity_product_id": opportunity_product_id,
                "pro_bono": pro_bono,
            },
        )

        db.session.add(campaign)
        db.session.commit()

        return campaign

    # PUT
    def approve_candidates(self):
        from takumi.services.offer import OfferService

        offers = Offer.query.filter(
            Offer.campaign == self.campaign, Offer.state == OFFER_STATES.CANDIDATE
        )
        for o in offers:
            OfferService(o).approve_candidate()

    def get_devices_grouped_by_locale(self, state):
        devices_and_users = (
            db.session.query(Device, User)
            .join(User)
            .join(Influencer)
            .join(Offer)
            .filter(Offer.campaign == self.campaign, Offer.state == state)
        ).all()

        def _group_by_request_locale(device_user):
            device, user = device_user
            return user.request_locale if user.request_locale else "en"

        return {
            locale: [device for (device, _user) in devices]
            for locale, devices in groupby(devices_and_users, _group_by_request_locale)
        }

    # PUT
    def revoke_requested_offers(self, state):
        from takumi.services.offer import OfferService

        offers = Offer.query.filter(Offer.campaign == self.campaign, Offer.state == state)
        devices_grouped_by_locale = self.get_devices_grouped_by_locale(state)

        for o in offers:
            OfferService(o).revoke(notify=False)

        for locale, devices in devices_grouped_by_locale.items():
            with locale_context(locale):
                client = NotificationClient(devices)
                client.send_rejection(
                    _(
                        'Unfortunately, you weren\'t selected for "%(campaign)s"',
                        campaign=self.campaign.name,
                    ),
                    self.campaign,
                )

    def _promote_to_accepted(self, state, force=False):
        from takumi.services import OfferService

        offers = Offer.query.filter(
            Offer.state == state, Offer.is_selected, Offer.campaign_id == self.campaign.id
        )

        if offers.count() == 0:
            raise CampaignPromotionException("No selected offers to promote")

        if not force:
            total_units = sum(self.campaign.fund.get_offer_units(offer) for offer in offers)
            if not self.campaign.fund.can_reserve_units(total_units):
                raise CampaignPromotionException(
                    "Trying to promote too many influencers, it would overflow the campaign"
                )

        for offer in offers:
            OfferService(offer).accept_request(ignore_campaign_limits=force)

        return offers

    def promote_selected_requested_to_accepted(self, force=False):
        self._promote_to_accepted(OFFER_STATES.REQUESTED, force=force)

    def promote_selected_approved_by_brand_to_accepted(self, force=False):
        self._promote_to_accepted(OFFER_STATES.APPROVED_BY_BRAND, force=force)

    def update_units(self, units):
        self.log.add_event("set_units", {"units": units})

    def update_shipping_required(self, shipping_required):
        self.log.add_event("set_shipping_required", {"shipping_required": shipping_required})

    def update_name(self, name):
        self.log.add_event("set_name", {"name": name.strip()})

    def update_description(self, description):
        self.log.add_event("set_description", {"description": description})

    def update_pictures(self, pictures):
        self.log.add_event("set_pictures", {"pictures": pictures})

    def update_prompts(self, prompts):
        prompts = _clean_and_validate_prompts(prompts)

        if self.campaign.prompts == prompts:
            # Prompts didn't change
            return

        self.log.add_event("set_prompts", {"prompts": prompts})

    def update_tags(self, tags):
        if tags is None:
            tags = []

        self.log.add_event("set_tags", {"tags": [t.lower() for t in tags]})

    def update_push_notification_message(self, push_notification_message):
        self.log.add_event(
            "set_push_notification_message",
            {"push_notification_message": push_notification_message},
        )

    def update_opportunity_product_id(self, opportunity_product_id):
        self.log.add_event(
            "set_opportunity_product_id", {"opportunity_product_id": opportunity_product_id}
        )

    def update_owner(self, owner_id):
        self.log.add_event("set_owner", {"owner_id": owner_id})

    def update_campaign_manager(self, campaign_manager_id):
        self.log.add_event("set_campaign_manager", {"campaign_manager_id": campaign_manager_id})

    def update_secondary_campaign_manager(self, secondary_campaign_manager_id):
        self.log.add_event(
            "set_secondary_campaign_manager",
            {"secondary_campaign_manager_id": secondary_campaign_manager_id},
        )

    def update_community_manager(self, community_manager_id):
        self.log.add_event("set_community_manager", {"community_manager_id": community_manager_id})

    def update_has_nda(self, has_nda):
        self.log.add_event("set_has_nda", {"has_nda": has_nda})

    def update_industry(self, industry):
        self.log.add_event("set_industry", {"industry": industry})

    def update_public(self, public):
        self.log.add_event("set_public", {"public": public})

    def update_pro_bono(self, pro_bono):
        if self.campaign.state != STATES.DRAFT:
            raise InvalidCampaignStateException("Campaign has to be draft to set pro bono")
        self.log.add_event("set_pro_bono", {"pro_bono": pro_bono})

    def update_brand_safety(self, brand_safety):
        if not brand_safety and len(self.campaign.offers) > 0:
            # Disallows turning off brand safety in launched campaigns if there are existing offers
            raise InvalidCampaignStateException(
                "Unable to turn off brand safety in campaign with existing offers"
            )
        self.log.add_event("set_brand_safety", {"brand_safety": brand_safety})

    def update_brand_match(self, brand_match):
        if not brand_match and len(self.campaign.offers) > 0:
            # Disallows turning off brand match in launched campaigns if there are existing offers
            raise InvalidCampaignStateException(
                "Unable to turn off brand match in campaign with existing offers"
            )
        self.log.add_event("set_brand_match", {"brand_match": brand_match})

    def update_extended_review(self, extended_review):
        if self.campaign.state != STATES.DRAFT and len(self.campaign.offers) > 0:
            raise InvalidCampaignStateException(
                "Campaign has to be in `draft` state in order to update extended review. Current state: {}".format(
                    self.campaign.state
                )
            )
        self.log.add_event("set_extended_review", {"extended_review": extended_review})

    def update_price(self, price):
        if price < 0:
            raise NegativePriceException("Price can't be negative")

        self.log.add_event("set_price", {"price": price})

    def update_list_price(self, list_price):
        if list_price < 0:
            raise NegativePriceException("List price can't be negative")
        elif self.campaign.state != STATES.DRAFT:
            raise InvalidCampaignStateException(
                "Campaign has to be in `draft` state in order to update list price. Current state: {}".format(
                    self.campaign.state
                )
            )

        self.log.add_event("set_list_price", {"list_price": list_price})

    def update_custom_reward_units(self, custom_reward_units):
        if self.campaign.state != STATES.DRAFT:
            raise InvalidCampaignStateException(
                "Campaign has to be in `draft` state in order to change reward base. Current state: {}".format(
                    self.campaign.state
                )
            )

        self.log.add_event("set_custom_reward_units", {"custom_reward_units": custom_reward_units})

    def update_require_insights(self, require_insights):
        self.log.add_event("set_require_insights", {"require_insights": require_insights})

    def stash(self):
        errors = Validate(self.campaign, StashSchema)
        if errors:
            raise CampaignStashException(errors)

        self.log.add_event("stash")

    def restore(self):
        if self.campaign.state != STATES.STASHED:
            raise InvalidCampaignStateException(
                "Campaign has to be in `stashed` state in order to restore. Current state: {}".format(
                    self.campaign.state
                )
            )

        self.log.add_event("restore")

    def launch(self):
        ignore_validators = []
        if self.campaign.pro_bono:
            ignore_validators = ["price", "list_price"]
            # XXX: Temporary hacky
            if self.campaign.price > 0 or self.campaign.list_price > 0:
                raise CampaignLaunchException("Campaign can't have a price if pro bono")
            if self.campaign.custom_reward_units and self.campaign.custom_reward_units > 0:
                raise CampaignLaunchException("Campaign can't have custom reward units if pro bono")

        errors = Validate(self.campaign, LaunchSchema, ignore_validators=ignore_validators)
        if errors:
            raise CampaignLaunchException(errors)

        # Make sure no defaults in briefs
        forbidden_paragraphs = [
            "This is a brief summary of the campaign",
            "This should be a short background of the brand",
            (
                "The main instructions for the campaign, you should add subsections as "
                "needed, to list for example specific story or post requirements"
            ),
            "Description of frame 1 requirements",
            "Description of frame 2 requirements",
            "Description of the caption requirements",
            "Description of carousel image 1 requirements",
            "Description of carousel image 2 requirements",
        ]
        for post in self.campaign.posts:
            for item in post.brief:
                if item.get("value") in forbidden_paragraphs:
                    raise CampaignLaunchException(
                        "You're trying to launch a campaign with some of the default brief text"
                    )

        self.log.add_event("launch")

    def send_notifications_to_all_targets(self, not_notified_in_the_last_hours=None):
        from takumi.tasks.campaign import notify_all_targeted

        if self.campaign.state != STATES.LAUNCHED:
            raise InvalidCampaignStateException(
                "Campaign has to be launched to send notifications to everyone"
            )
        if (
            self.campaign.submission_deadline
            and self.campaign.submission_deadline < dt.datetime.now(dt.timezone.utc)
        ):
            raise ServiceException("A submission deadline for the campaign has already passed")
        if self.campaign.deadline and self.campaign.deadline < dt.datetime.now(dt.timezone.utc):
            raise ServiceException("A deadline for the campaign has already passed")

        notify_all_targeted.delay(self.campaign.id, not_notified_in_the_last_hours)

    def notify_devices(self, devices):
        campaign = self.campaign
        message = campaign.push_notification_message or "New campaign opportunity from {}".format(
            campaign.advertiser.name
        )
        for device in devices:
            notification = Notification(
                campaign_id=campaign.id, device_id=device.id, message=message
            )
            db.session.add(notification)

        client = NotificationClient(devices)
        client.send_campaign(message, campaign)

    def new_report_token(self):
        self.log.add_event(
            "set_report_token", {"old_token": self.campaign.report_token, "new_token": uuid4_str()}
        )

    def preview(self, username):
        influencer = Influencer.by_username(username)
        if influencer is None:
            raise InfluencerNotFound(f"No influencer found with the username {username}")
        token = url_signer.dumps(str(self.campaign.id), salt="preview_campaign")
        if not influencer.has_device:
            raise CampaignPreviewException("No device found for influencer")

        client = NotificationClient.from_influencer(influencer)
        client.send_campaign(f"Preview {self.campaign.name}", self.campaign, token=token)

    def complete(self):
        errors = Validate(self.campaign, CompleteSchema)
        if errors:
            raise CampaignCompleteException(errors)
        self.log.add_event("complete")

    def refresh_candidates_order(self):
        """Refresh the list of offers in the candidate order

        Sets the list to the existing order and any missing ones added at the end
        """
        offer_q = self.campaign.ordered_candidates_q.with_entities(Offer.id)
        self.campaign.candidate_order = [offer.id for offer in offer_q]

    def set_new_candidate_position(self, from_offer_id, to_offer_id, hash=None):
        """Move an offer id in the order to the position of another offer id"""
        with db.session.begin_nested():
            # Refresh the order, so it's up to date
            self.refresh_candidates_order()

            if (
                to_offer_id not in self.campaign.candidate_order
                or from_offer_id not in self.campaign.candidate_order
            ):
                raise InvalidOfferIdException("Offer ids not found in order")

        if hash != self.campaign.candidates_hash:
            raise OrderHasUpdatedException("Candidate order is stale, please reload the list")

        position = self.campaign.candidate_order.index(to_offer_id)

        new_order = [
            offer_id for offer_id in self.campaign.candidate_order if offer_id != from_offer_id
        ]
        new_order.insert(position, from_offer_id)

        self.campaign.candidate_order = new_order

    def update_report_summary(self, summary):
        self.log.add_event("set_report_summary", {"summary": summary or None})
