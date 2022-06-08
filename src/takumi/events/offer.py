import datetime as dt

from takumi.events import Event, TableLog
from takumi.models import OfferEvent
from takumi.models.offer import STATES
from takumi.notifications import NotificationClient


class CreateOffer(Event):
    start_state = None
    end_state = STATES.PENDING

    def apply(self, offer):
        offer.campaign_id = self.properties["campaign_id"]
        offer.influencer_id = self.properties["influencer_id"]
        offer.reward = self.properties["reward"]
        offer.followers_per_post = self.properties["followers_per_post"]
        offer.engagements_per_post = self.properties["engagements_per_post"]
        offer.estimated_engagements_per_post = self.properties["engagements_per_post"]
        offer.vat_percentage = self.properties["vat_percentage"]


class CreateOfferInvite(CreateOffer):
    start_state = None
    end_state = STATES.INVITED


class RequestParticipation(Event):
    start_state = STATES.PENDING
    end_state = STATES.REQUESTED

    def apply(self, offer):
        offer.answers = self.properties.get("answers", [])


class AcceptRequestedParticipation(Event):
    start_state = (STATES.REQUESTED, STATES.APPROVED_BY_BRAND)
    end_state = STATES.ACCEPTED

    def apply(self, offer):
        offer.accepted = dt.datetime.now(dt.timezone.utc)


class ReserveOffer(Event):
    start_state = STATES.INVITED
    end_state = STATES.ACCEPTED

    def apply(self, offer):
        offer.followers_per_post = offer.influencer.instagram_account.followers
        offer.accepted = dt.datetime.now(dt.timezone.utc)
        offer.answers = self.properties.get("answers", [])


class ForceReserveOffer(Event):
    end_state = STATES.ACCEPTED

    def apply(self, offer):
        offer.followers_per_post = offer.influencer.instagram_account.followers
        offer.accepted = dt.datetime.now(dt.timezone.utc)


class RevokeOffer(Event):
    start_state = (
        STATES.PENDING,
        STATES.INVITED,
        STATES.ACCEPTED,
        STATES.REQUESTED,
        STATES.APPROVED_BY_BRAND,
        STATES.CANDIDATE,
    )
    end_state = STATES.REVOKED

    def apply(self, offer):
        pass


class RenewOffer(Event):
    """This is essentially an "undo" for revoked offers, in case a community
    manager accidentally or erroneously revokes an offer, which should be made
    available to the influencer again.
    """

    start_state = STATES.REVOKED
    end_state = STATES.INVITED

    def apply(self, offer):
        pass


class MarkDispatched(Event):
    start_state = STATES.ACCEPTED

    def apply(self, offer):
        offer.in_transit = True

        if "tracking_code" in self.properties:
            offer.tracking_code = self.properties["tracking_code"]


class RejectOffer(Event):
    start_state = (STATES.INVITED, STATES.ACCEPTED, STATES.REQUESTED, STATES.PENDING)
    end_state = STATES.REJECTED

    def apply(self, offer):
        pass


class SetClaimable(Event):
    start_start = STATES.ACCEPTED

    def apply(self, offer):
        offer.is_claimable = True
        offer.payable = dt.datetime.now(
            dt.timezone.utc
        )  # whatever it was before, record the right time


class UnsetClaimable(Event):
    def apply(self, offer):
        offer.is_claimable = False
        offer.payable = None


class SendPushNotification(Event):
    start_state = (STATES.INVITED, STATES.ACCEPTED, STATES.PENDING)

    def apply(self, offer):
        client = NotificationClient.from_influencer(offer.influencer)
        client.send_offer(offer, message=self.properties["message"])


class UpdateReward(Event):
    def apply(self, offer):
        offer.reward = self.properties["reward"]


class LastGigSubmitted(Event):
    def apply(self, offer):
        offer.payable = self.properties["payable"]


class SetSubmissionDeadline(Event):
    def apply(self, offer):
        offer.submission_deadline = self.properties["deadline"]


class SetIsSelected(Event):
    def apply(self, offer):
        offer.is_selected = self.properties["is_selected"]


class UpdateEngagement(Event):
    """One of the gigs attached to the offer has had it's engagement updated via
    the 'set_interaction' event.  XXX: This is a prime candidate for the "OfferLog"
    reacting to Gig events in a centralized bus?
    """

    def apply(self, offer):
        offer.engagements_per_post = self.properties["engagements_per_post"]


class SetAsCandidate(Event):
    start_state = STATES.REQUESTED
    end_state = STATES.CANDIDATE

    def apply(self, offer):
        pass


class ApproveCandidate(Event):
    start_state = STATES.CANDIDATE
    end_state = STATES.APPROVED_BY_BRAND

    def apply(self, offer):
        pass


class RejectCandidate(Event):
    start_state = STATES.CANDIDATE
    end_state = STATES.REJECTED_BY_BRAND

    def apply(self, offer):
        pass


class RevertRejection(Event):
    start_state = (STATES.REJECTED, STATES.REVOKED, STATES.REJECTED_BY_BRAND)

    def apply(self, offer):
        """A event that reverts a prior rejection

        Takes in a state as a parameter and sets the state to it. It's expected
        that the provided state will be valid.
        """
        offer.state = self.properties["state"]


class SetFollowersPerPost(Event):
    def apply(self, offer):
        offer.followers_per_post = self.properties["followers"]


class OfferLog(TableLog):
    event_model = OfferEvent
    relation = "offer"
    type_map = {
        "accept_requested_participation": AcceptRequestedParticipation,
        "approve_candidate": ApproveCandidate,
        "create": CreateOffer,
        "create_invite": CreateOfferInvite,
        "force_reserve": ForceReserveOffer,
        "last_gig_submitted": LastGigSubmitted,
        "mark_dispatched": MarkDispatched,
        "reject": RejectOffer,
        "reject_candidate": RejectCandidate,
        "renew": RenewOffer,
        "request_participation": RequestParticipation,
        "reserve": ReserveOffer,
        "revert_rejection": RevertRejection,
        "revoke": RevokeOffer,
        "send_push_notification": SendPushNotification,
        "set_as_candidate": SetAsCandidate,
        "set_claimable": SetClaimable,
        "set_followers_per_post": SetFollowersPerPost,
        "set_is_selected": SetIsSelected,
        "set_submission_deadline": SetSubmissionDeadline,
        "unset_claimable": UnsetClaimable,
        "update_engagement": UpdateEngagement,
        "update_reward": UpdateReward,
    }
