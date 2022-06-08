import datetime as dt
from typing import List, Optional

from takumi.campaigns import campaign_reserve_state
from takumi.error_codes import (
    CAMPAIGN_NOT_LAUNCHED_ERROR_CODE,
    CAMPAIGN_NOT_RESERVABLE_ERROR_CODE,
    CAMPAIGN_REQUIRES_REQUEST_ERROR_CODE,
    INFLUENCER_NOT_ELIGIBLE_ERROR_CODE,
    INVALID_OFFER_STATE_ERROR_CODE,
    OFFER_REWARD_CHANGED_ERROR_CODE,
    UNREJECTABLE_OFFER_ERROR_CODE,
)
from takumi.events.offer import OfferLog
from takumi.extensions import db
from takumi.i18n import gettext as _
from takumi.i18n import locale_context
from takumi.models import Comment, Config, Notification, Offer, OfferEvent, UserCommentAssociation
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.influencer import STATES as INFLUENCER_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.notifications import NotificationClient
from takumi.rewards import RewardCalculator
from takumi.schedule.period import DateTimePeriod
from takumi.services import Service
from takumi.services.exceptions import (
    AlreadyRequestedException,
    ApplyFirstException,
    CampaignFullyReservedException,
    CampaignNotLaunchedException,
    CampaignRequiresRequestForParticipation,
    InfluencerNotEligibleException,
    InfluencerOnCooldownForAdvertiserException,
    InvalidAnswersException,
    OfferAlreadyClaimed,
    OfferAlreadyExistsException,
    OfferNotClaimableException,
    OfferNotDispatchableException,
    OfferNotRejectableException,
    OfferNotReservableException,
    OfferPushNotificationException,
    OfferRewardChangedException,
    ServiceException,
)
from takumi.tasks.instagram_account import update_latest_posts

from .campaign import CampaignService
from .influencer import InfluencerService


def validate_answers(prompts, answers):
    if prompts == []:
        return

    if answers is None or len(prompts) != len(answers):
        raise InvalidAnswersException(_("You need to answer all the prompts to participate!"))

    prompts = sorted(prompts, key=lambda x: x["text"])
    answers = sorted(answers, key=lambda x: x["prompt"])

    for prompt, answer in zip(prompts, answers):
        if prompt["type"] == "confirmation":
            if len(prompt["choices"]) != len(answer["answer"]):
                raise InvalidAnswersException(_("All confirmations need to be accepted!"))
        else:
            answer_choices = answer["answer"]
            answer_text = "".join(answer_choices).strip()
            if len(answer_choices) == 0 or answer_text == "":
                raise InvalidAnswersException(
                    _("You need to answer '%(prompt)s'", prompt=prompt["text"])
                )


class OfferService(Service):
    """
    Represents the business model for Offer. This is the bridge between
    the database and the application.
    """

    SUBJECT = Offer
    LOG = OfferLog

    @property
    def offer(self) -> Offer:
        return self.subject

    # GET
    @staticmethod
    def get_by_id(offer_id) -> Optional[Offer]:
        return Offer.query.get(offer_id)

    @staticmethod
    def get_top_offers_in_campaign(campaign_id: str) -> Optional[List[Offer]]:
        """A method that filters all accepted offers related to a specific campaign,
        is ranked descending by ER in-feed and capped at the top three.

        Note:
            One offer has one creator, therefore, together with all continents of one offer,
            we get a specific Creator.

        Args:
            campaign_id: The campaign's id.

        Returns:
            List of filtered and sorted offers.
        """
        return (
            Offer.query.filter(
                Offer.campaign_id == campaign_id,
                Offer.state == OFFER_STATES.ACCEPTED,
                Offer.engagement_rate_static != 0,
            )
            .order_by(Offer.engagement_rate_static.desc().nullslast())  # type: ignore
            .limit(3)
            .all()
        )

    @staticmethod
    def get_for_influencer_in_campaign(influencer_id, campaign_id) -> Optional[Offer]:
        return Offer.query.filter(
            Offer.influencer_id == influencer_id, Offer.campaign_id == campaign_id
        ).one_or_none()

    @staticmethod
    def get_push_notifications(offer_id):
        return (
            OfferEvent.query.join(Offer)
            .filter(OfferEvent.type == "send_push_notification", Offer.id == offer_id)
            .with_entities(OfferEvent.created)
            .order_by(OfferEvent.created.desc())
        ).all()

    @staticmethod
    def get_revoke_event(id):
        return (
            OfferEvent.query.filter(OfferEvent.offer_id == id, OfferEvent.type == "revoke")
            .order_by(OfferEvent.created.desc())
            .first()
        )

    @staticmethod
    def get_rejected_date(id):
        """Rejected date is the date that an offer was one of:

        1. Rejected by influencer
        2. Revoked by Takumi
        3. Rejected by a client
        """
        return (
            OfferEvent.query.filter(
                OfferEvent.offer_id == id,
                OfferEvent.type.in_(("reject", "revoke", "reject_candidate")),
            )
            .with_entities(OfferEvent.created)
            .order_by(OfferEvent.created.desc())
            .limit(1)
            .scalar()
        )

    @staticmethod
    def get_from_filter(
        filter_by=tuple(), order_by=tuple(), with_entities=(Offer,), limit=None, method="all"
    ):
        return getattr(
            Offer.query.filter(*filter_by)
            .order_by(*order_by)
            .with_entities(*with_entities)
            .limit(limit),
            method,
        )()

    @classmethod  # NOQA: C901
    def create(cls, campaign_id, influencer_id, reward=None, skip_targeting=False):
        influencer = InfluencerService.get_by_id(influencer_id)
        campaign = CampaignService.get_by_id(campaign_id)

        if influencer is None:
            raise ServiceException(f"<Influencer: {influencer_id}> not found")

        if campaign is None:
            raise ServiceException(f"<Campaign: {campaign_id}> not found")

        if reward is None:
            reward = RewardCalculator(campaign).calculate_reward_for_influencer(influencer)

        if not campaign.fund.is_reservable():
            raise CampaignFullyReservedException("Campaign is already fully reserved")

        if campaign.advertiser.on_cooldown(influencer):
            raise InfluencerOnCooldownForAdvertiserException(
                'Influencer: "{}" is on cooldown for advertiser "{}"'.format(
                    influencer.username, campaign.advertiser.name
                )
            )

        if campaign.submission_deadline and campaign.submission_deadline < dt.datetime.now(
            dt.timezone.utc
        ):
            raise ServiceException("A submission deadline for the campaign has already passed")
        if campaign.deadline and campaign.deadline < dt.datetime.now(dt.timezone.utc):
            raise ServiceException("A deadline for the campaign has already passed")

        existing_offer = cls.get_for_influencer_in_campaign(influencer.id, campaign.id)
        if existing_offer is not None:
            raise OfferAlreadyExistsException(
                "<Influencer {}> already has an offer (<Offer {}>) for <Campaign {}>".format(
                    influencer.id, existing_offer.id, campaign.id
                )
            )

        if not skip_targeting:
            influencer_eligible_for_campaign = (
                influencer.state in (INFLUENCER_STATES.VERIFIED, INFLUENCER_STATES.REVIEWED)
                and influencer.is_eligible
                and campaign.targeting.targets_influencer(influencer)
            )

            if not influencer_eligible_for_campaign:
                raise InfluencerNotEligibleException(
                    "Influencer is not eligible", INFLUENCER_NOT_ELIGIBLE_ERROR_CODE
                )
        if influencer.target_region:
            vat_percentage = influencer.target_region.get_vat_percentage(
                dt.datetime.now(dt.timezone.utc).date()
            )
        else:
            vat_percentage = None

        offer = Offer()
        log = OfferLog(offer)

        if influencer.instagram_account:
            followers_per_post = influencer.instagram_account.followers
        else:
            followers_per_post = 0

        log.add_event(
            "create" if campaign.apply_first else "create_invite",
            {
                "campaign_id": campaign.id,
                "influencer_id": influencer.id,
                "vat_percentage": vat_percentage,
                "reward": reward,
                "followers_per_post": followers_per_post,
                "engagements_per_post": influencer.estimated_engagements_per_post,
            },
        )

        db.session.add(offer)
        db.session.commit()

        # Trigger an update of latest posts for the influencer
        if influencer.instagram_account:
            update_latest_posts.delay(influencer.instagram_account.id)

        return offer

    # PUT
    def make_comment(self, content, creator):
        self.offer.comments.append(Comment.create(content, creator, self.offer))

    def mark_comments_as_seen_by(self, user):
        for comment in self.offer.comments:
            if not comment.seen_by_user(user.id):
                UserCommentAssociation.create(user, comment)

    def revoke(self, notify=True):
        if self.offer.is_claimable:
            raise ServiceException("Can't revoke a claimable offer")
        if self.offer.state not in (
            OFFER_STATES.PENDING,
            OFFER_STATES.INVITED,
            OFFER_STATES.ACCEPTED,
            OFFER_STATES.REQUESTED,
            OFFER_STATES.APPROVED_BY_BRAND,
            OFFER_STATES.CANDIDATE,
        ):
            raise ServiceException(f"Can't revoke a {self.offer.state} offer")
        self.log.add_event("revoke")

        if notify:
            influencer = self.offer.influencer
            if self.offer.state == OFFER_STATES.REQUESTED and influencer.has_device:
                client = NotificationClient.from_influencer(influencer)
                with locale_context(influencer.user.request_locale):
                    client.send_rejection(
                        _(
                            'Unfortunately, you weren\'t selected for "%(campaign)s"',
                            campaign=self.offer.campaign.name,
                        ),
                        self.offer.campaign,
                    )

    def renew(self):
        self.log.add_event("renew")

    def request_participation(self, answers=[], ignore_prompts=False):
        from takumi.services.influencer import FetchingAudienceInsightsFailed, InfluencerService

        influencer = self.offer.influencer
        user = influencer.user
        campaign = self.offer.campaign

        if user.facebook_account:
            try:
                InfluencerService(self.offer.influencer).fetch_and_save_audience_insights()
            except FetchingAudienceInsightsFailed:
                pass

        if campaign.requires_tiktok_account and not influencer.user.tiktok_username:
            raise ServiceException(
                "This campaign requires a TikTok account. Please configure a TikTok username in your profile."
            )
        if self.offer.campaign.requires_facebook:
            if not influencer.info.get("FACEBOOK_PAGE_SKIP_CAMPAIGN_CHECK", False) and (
                not influencer.user.facebook_account or not influencer.user.facebook_account.active
            ):
                raise ServiceException("Please link your Facebook account")
        if self.offer.state == OFFER_STATES.REQUESTED:
            raise AlreadyRequestedException("Participation has already been requested")
        if self.offer.state == OFFER_STATES.REJECTED:
            raise ServiceException("Offer has already been rejected")

        if not ignore_prompts:
            validate_answers(campaign.prompts, answers)

        self.log.add_event("request_participation", {"answers": answers})

        from takumi.tasks import audit as audit_tasks

        config = Config.get("PROCESS_HYPEAUDITOR_REPORTS")
        if config and config.value is True:
            audit_tasks.create_audit.delay(influencer_id=self.offer.influencer.id)

    def reserve(self, answers=[]):
        with campaign_reserve_state(self.offer.campaign):
            if self.offer.campaign.apply_first:
                raise CampaignRequiresRequestForParticipation(
                    "Campaign needs to be requested for participation",
                    CAMPAIGN_REQUIRES_REQUEST_ERROR_CODE,
                )
            if not self.offer.campaign.fund.is_reservable():
                raise CampaignFullyReservedException(
                    "Campaign is already fully reserved", CAMPAIGN_NOT_RESERVABLE_ERROR_CODE
                )

            if self.offer.campaign.state != CAMPAIGN_STATES.LAUNCHED:
                raise CampaignNotLaunchedException(
                    "Campaign isn't launched yet!", CAMPAIGN_NOT_LAUNCHED_ERROR_CODE
                )

            if self.offer.state != OFFER_STATES.INVITED:
                raise OfferNotReservableException(
                    f"Cannot reserve {self.offer.state} offer",
                    INVALID_OFFER_STATE_ERROR_CODE,
                )

            if any(post.deadline_passed for post in self.offer.campaign.posts):
                raise OfferNotReservableException("Deadline has already passed in this campaign")

            if self.offer.campaign.reward_model == "reach":
                current_reward = RewardCalculator(
                    self.offer.campaign
                ).calculate_reward_for_influencer(self.offer.influencer)
                if current_reward != self.offer.reward:
                    self.update_reward(current_reward)
                    db.session.commit()

                    raise OfferRewardChangedException(
                        "There's limited space left on this campaign, so we're not able to offer the full reward",
                        OFFER_REWARD_CHANGED_ERROR_CODE,
                    )
            validate_answers(self.offer.campaign.prompts, answers)
            self.log.add_event("reserve", {"answers": answers})

        from takumi.tasks import audit as audit_tasks

        config = Config.get("PROCESS_HYPEAUDITOR_REPORTS")
        if config and config.value is True:
            audit_tasks.create_audit.delay(influencer_id=self.offer.influencer.id)

    def force_reserve(self):
        with campaign_reserve_state(self.offer.campaign):
            if self.offer.state not in [
                OFFER_STATES.PENDING,
                OFFER_STATES.INVITED,
                OFFER_STATES.REJECTED,
                OFFER_STATES.REVOKED,
            ]:
                raise OfferNotReservableException(
                    f"Cannot force reserve {self.offer.state} offer",
                    INVALID_OFFER_STATE_ERROR_CODE,
                )
            if not self.offer.campaign.fund.is_reservable():
                raise CampaignFullyReservedException(
                    "Campaign is already fully reserved", CAMPAIGN_NOT_RESERVABLE_ERROR_CODE
                )

            if self.offer.campaign.state != CAMPAIGN_STATES.LAUNCHED:
                raise CampaignNotLaunchedException(
                    "Campaign isn't launched yet!", CAMPAIGN_NOT_LAUNCHED_ERROR_CODE
                )

            if any(post.deadline_passed for post in self.offer.campaign.posts):
                raise OfferNotReservableException("Deadline has already passed in this campaign")

            if self.offer.campaign.shipping_required:
                # Confirm the shipping address
                address = self.offer.influencer.address

                if address:
                    address.modified = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
                        minutes=1
                    )  # XXX: Horrible race condition here
                    db.session.add(address)

            self.log.add_event("force_reserve")

    def accept_request(self, ignore_campaign_limits=False):
        with campaign_reserve_state(self.offer.campaign):
            if (
                self.offer.campaign.brand_match
                and self.offer.state != OFFER_STATES.APPROVED_BY_BRAND
            ):
                raise OfferNotReservableException(
                    "Cannot accept {} offer. It needs to be brand approved first".format(
                        self.offer.state
                    ),
                    INVALID_OFFER_STATE_ERROR_CODE,
                )
            if self.offer.state not in [OFFER_STATES.APPROVED_BY_BRAND, OFFER_STATES.REQUESTED]:
                raise OfferNotReservableException(
                    "Cannot accept {} offer. It needs to be accepted by the influencer".format(
                        self.offer.state
                    ),
                    INVALID_OFFER_STATE_ERROR_CODE,
                )
            if not self.offer.campaign.fund.is_reservable() and not ignore_campaign_limits:
                raise CampaignFullyReservedException(
                    "Campaign is already fully reserved", CAMPAIGN_NOT_RESERVABLE_ERROR_CODE
                )

            if self.offer.campaign.state != CAMPAIGN_STATES.LAUNCHED:
                raise CampaignNotLaunchedException(
                    "Campaign isn't launched yet!", CAMPAIGN_NOT_LAUNCHED_ERROR_CODE
                )

            if any(post.deadline_passed for post in self.offer.campaign.posts):
                raise OfferNotReservableException("Deadline has already passed in this campaign")

            self.log.add_event("accept_requested_participation")
            if self.offer.influencer.has_device:
                self.send_push_notification(
                    _(
                        'You have been accepted into the campaign "%(campaign)s"',
                        campaign=self.offer.campaign.name,
                    )
                )

            # Clear selected flag if it was set
            if self.offer.is_selected:
                self.set_is_selected(False)

    def update_reward(self, reward):
        if self.offer.claimed:
            raise OfferAlreadyClaimed("Offer has already been claimed")

        self.log.add_event("update_reward", {"reward": reward})

    def reject(self):
        if not self.offer.can_reject():
            raise OfferNotRejectableException(
                "This offer cannot be rejected", UNREJECTABLE_OFFER_ERROR_CODE
            )
        OfferLog(self.offer).add_event("reject")

    def mark_dispatched(self, tracking_code=None):
        if not self.offer.campaign.shipping_required:
            raise OfferNotDispatchableException(
                "Can't dispatch an offer for a campaign without shipping"
            )

        if self.offer.state != OFFER_STATES.ACCEPTED:
            raise OfferNotDispatchableException("Can't dispatch an offer that hasn't been accepted")

        properties = {}
        if tracking_code:
            properties["tracking_code"] = tracking_code

        OfferLog(self.offer).add_event("mark_dispatched", properties)

    def set_claimable(self, force=False):
        if not force:
            if self.offer.state != OFFER_STATES.ACCEPTED:
                raise OfferNotClaimableException(
                    f"Cannot set {self.offer.state} offer as claimable",
                    INVALID_OFFER_STATE_ERROR_CODE,
                )
            if not self.offer.has_all_gigs_claimable():
                raise OfferNotClaimableException(
                    "All gigs need to have passed the review period in order to become claimable"
                )
        self.log.add_event("set_claimable")

    def unset_claimable(self):
        self.log.add_event("unset_claimable")

    def last_gig_submitted(self):
        claimable_time = self.offer.get_claimable_time()
        if not claimable_time:
            return None

        OfferLog(self.offer).add_event("last_gig_submitted", {"payable": claimable_time})

        if self.offer.campaign.pro_bono:
            # Create Takumi payment to mark gig as paid out
            from takumi.models.payment import STATES as PAYMENT_STATES
            from takumi.services import PaymentService

            self.offer.is_claimable = True
            payment = PaymentService.create(
                self.offer.id, {"destination": {"type": "takumi", "value": "pro-bono"}}
            )
            payment.successful = True
            payment.state = PAYMENT_STATES.PAID

    def send_push_notification(self, message=None):
        if not self.offer.influencer.has_device:
            raise OfferPushNotificationException(
                f"Influencer {self.offer.influencer.username} has no registered device"
            )
        if self.offer.state not in (
            OFFER_STATES.PENDING,
            OFFER_STATES.ACCEPTED,
            OFFER_STATES.INVITED,
        ):
            raise OfferPushNotificationException(
                f"Cannot send a push notification for offer in {self.offer.state} state",
                INVALID_OFFER_STATE_ERROR_CODE,
            )
        if self.offer.has_all_gigs():
            raise OfferPushNotificationException(
                "Offer already has all gigs. Cannot send push notification"
            )
        if self.offer.campaign.state != CAMPAIGN_STATES.LAUNCHED:
            raise OfferPushNotificationException(
                "Can't send a push notification for a campaign in {} state. Campaign needs to be launched".format(
                    self.offer.campaign.state
                )
            )

        message = (
            message
            or self.offer.campaign.push_notification_message
            or f"New campaign opportunity from {self.offer.campaign.advertiser.name}"
        )
        self.log.add_event("send_push_notification", {"message": message})
        db.session.add(
            Notification(
                campaign_id=self.offer.campaign.id,
                device_id=self.offer.influencer.device.id,
                message=message,
            )
        )

    def extend_submission_deadline(self, hours):
        if self.offer.submission_deadline is None:
            raise Exception()  # XXX: No deadline on the offer

        self.log.add_event(
            "set_submission_deadline",
            {"deadline": DateTimePeriod(hours).after(self.offer.submission_deadline)},
        )

    def update_engagements_per_post(self):
        new_engagement = self.offer.calculate_engagements_per_post()
        self.log.add_event(
            "update_engagement",
            {
                "engagements_per_post": new_engagement,
                "old_engagements_per_post": self.offer.engagements_per_post,
            },
        )

    def set_is_selected(self, is_selected):
        campaign = self.offer.campaign
        if not campaign.apply_first:
            raise ApplyFirstException("Only Apply First campaigns have selected")

        self.log.add_event("set_is_selected", {"is_selected": is_selected})

    def set_as_candidate(self):
        campaign = self.offer.campaign
        campaign.candidates_submitted = dt.datetime.now(dt.timezone.utc)

        if not campaign.apply_first:
            raise ApplyFirstException("Only apply first campaigns have candidates")

        self.log.add_event("set_as_candidate")

        # Clear selected if it was set
        if self.offer.is_selected:
            self.set_is_selected(False)

    def approve_candidate(self):
        campaign = self.offer.campaign

        if not campaign.apply_first:
            raise ApplyFirstException("Only apply first campaigns have candidates")

        self.log.add_event("approve_candidate")

    def reject_candidate(self, reason):
        campaign = self.offer.campaign

        if not campaign.apply_first:
            raise ApplyFirstException("Only apply first campaigns have candidates")

        self.log.add_event("reject_candidate", {"reason": reason})

        influencer = self.offer.influencer
        if influencer.has_device:
            client = NotificationClient.from_influencer(influencer)
            with locale_context(influencer.user.request_locale):
                client.send_rejection(
                    _(
                        'Unfortunately, you weren\'t selected for "%(campaign)s"',
                        campaign=self.offer.campaign.name,
                    ),
                    self.offer.campaign,
                )

    def revert_rejection(self):
        """Revert a rejected offer into its previous state

        Rejected offers include offers in the following states;
            * Rejected by the influencer
            * Rejected by the brand
            * Revoked by brand

        """
        if self.offer.state == OFFER_STATES.REJECTED:
            event_type = "reject"
        elif self.offer.state == OFFER_STATES.REJECTED_BY_BRAND:
            event_type = "reject_candidate"
        elif self.offer.state == OFFER_STATES.REVOKED:
            event_type = "revoke"
        else:
            raise ServiceException("Offer has to be rejected or revoked to revert rejection")

        event = (
            OfferEvent.query.filter(
                OfferEvent.offer == self.offer, OfferEvent.type == event_type
            ).order_by(OfferEvent.event["_created"].astext.desc())
        ).first()
        if event is None:
            raise ServiceException("Unable to find the rejection event")

        previous_state = event.event.get("_from_state")

        if previous_state is None:
            raise ServiceException("Previous state unknown, please contact support")
        elif previous_state == OFFER_STATES.ACCEPTED:
            campaign = self.offer.campaign
            units = campaign.fund.get_offer_units(self.offer)
            if not campaign.fund.can_reserve_units(units):
                raise ServiceException("Not enough space on the campaign to revert rejection")

        self.log.add_event("revert_rejection", {"state": previous_state})

    def set_followers_per_post(self, followers):
        """Set followers per post, if no content is live

        Followers per post is used to estimate reach for a campaign, after the
        content is live, the followers at time of posting should be used
        instead
        """

        if any(
            gig.instagram_post is not None
            or (gig.instagram_story is not None and gig.instagram_story.posted)
            for gig in self.offer.gigs
        ):
            raise ServiceException(
                "Unable to set followers per post if any content posted on Instagram"
            )

        self.log.add_event("set_followers_per_post", {"followers": followers})
