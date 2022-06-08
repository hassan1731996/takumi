import datetime as dt
from typing import Optional

from takumi import slack
from takumi.events.gig import GigLog
from takumi.extensions import db
from takumi.models import Gig, Media, Offer, Submission
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.post import PostTypes
from takumi.roles.roles import AdvertiserRole
from takumi.services import Service
from takumi.services.exceptions import (
    GigAlreadySubmittedException,
    GigInvalidCaptionException,
    GigInvalidStateException,
    GigReportException,
    GigResubmissionException,
    GigSkipException,
    GigUpdateCaptionException,
    OfferNotAcceptedException,
    OfferNotFoundException,
    PostNotFoundException,
    UserNotFoundException,
)
from takumi.utils import uuid4_str
from takumi.validation.errors import MultipleErrorsError
from takumi.validation.media import ConditionsValidator


class GigService(Service):
    """
    Represents the business model for Gig. This isolates the database
    from the application.
    """

    SUBJECT = Gig
    LOG = GigLog

    @property
    def gig(self):
        return self.subject

    # GET
    @staticmethod
    def get_by_id(id: str) -> Optional[Gig]:
        return Gig.query.get(id)

    @staticmethod
    def get_by_offer_and_post(offer_id: str, post_id: str) -> Optional[Gig]:
        return (
            Gig.query.filter(Gig.offer_id == offer_id, Gig.post_id == post_id)
            .order_by(Gig.created.desc())
            .one_or_none()
        )

    @staticmethod
    def _get_latest_influencer_gig_of_a_post(
        influencer_id: str, post_id: str, state: Optional[str] = None
    ) -> Optional[Gig]:
        query = (
            Gig.query.join(Offer)
            .filter(Gig.post_id == post_id, Offer.influencer_id == influencer_id)
            .order_by(Gig.created.desc())
        )
        if state:
            query.filter(Gig.state == state)

        return query.first()

    @staticmethod
    def get_latest_influencer_gig_of_a_post(influencer_id: str, post_id: str) -> Optional[Gig]:
        return GigService._get_latest_influencer_gig_of_a_post(influencer_id, post_id)

    @staticmethod
    def get_latest_influencer_require_resubmit_gig_of_a_post(
        influencer_id: str, post_id: str
    ) -> Optional[Gig]:
        return GigService._get_latest_influencer_gig_of_a_post(
            influencer_id, post_id, GIG_STATES.REQUIRES_RESUBMIT
        )

    def verify_gig(self, reviewer_id):
        from takumi.services import UserService

        if not UserService.get_by_id(reviewer_id):
            raise UserNotFoundException("User not found")

        if not self.gig.instagram_post and not self.gig.instagram_story:
            raise GigInvalidStateException("Gig has not been linked to Instagram Content")

        if self.gig.instagram_story and not self.gig.instagram_story.has_marked_frames:
            raise GigInvalidStateException("Story frames have not been picked")

        self.log.add_event(
            "mark_as_verified",
            {"reviewer_id": reviewer_id, "review_date": dt.datetime.now(dt.timezone.utc)},
        )

    def review_gig(self, reviewer_id):
        from takumi.services import UserService

        if not UserService.get_by_id(reviewer_id):
            raise UserNotFoundException("User not found")

        if self.gig.state != GIG_STATES.SUBMITTED:
            raise GigInvalidStateException("Only gigs submitted for review can be reviewed")

        self.log.add_event(
            "review", {"reviewer_id": reviewer_id, "review_date": dt.datetime.now(dt.timezone.utc)}
        )

        if not self.gig.post.campaign.brand_safety:
            self.log.add_event(
                "approve",
                {"approver_id": reviewer_id, "approve_date": dt.datetime.now(dt.timezone.utc)},
            )

    def review_approved_gig(self, reviewer_id):
        from takumi.services import UserService

        if not UserService.get_by_id(reviewer_id):
            raise UserNotFoundException("User not found")

        if self.gig.state != GIG_STATES.APPROVED:
            raise GigInvalidStateException("Event gigs can only be reviewed when approved")

        self.log.add_event(
            "review_approved_gig",
            {"reviewer_id": reviewer_id, "review_date": dt.datetime.now(dt.timezone.utc)},
        )

    def reject(self, reason):
        from takumi.services import OfferService

        gig = self.gig

        self.log.add_event("reject", {"reason": reason})

        if gig.offer.has_all_gigs_claimable():
            with OfferService(gig.offer) as service:
                service.set_claimable()

    def approve_gig(self, approver_id):
        from takumi.services import UserService

        if self.gig.state != GIG_STATES.REVIEWED:
            raise GigInvalidStateException("Only reviewed gigs can be approved")

        if not UserService.get_by_id(approver_id):
            raise UserNotFoundException("User not found")

        self.log.add_event(
            "approve",
            {"approver_id": approver_id, "approve_date": dt.datetime.now(dt.timezone.utc)},
        )

    @classmethod  # noqa: C901
    def create(cls, offer_id, post_id):
        from takumi.services import OfferService, PostService

        offer = OfferService.get_by_id(offer_id)
        post = PostService.get_by_id(post_id)

        if not offer:
            raise OfferNotFoundException("Could not find offer")

        campaign = offer.campaign

        if not post:
            raise PostNotFoundException("Could not find post")

        if post not in campaign.posts:
            raise PostNotFoundException("Post does not belong to this Offer")

        if offer.state not in OFFER_STATES.ACCEPTED:
            raise OfferNotAcceptedException("Offer is not in accepted state")

        if cls.get_by_offer_and_post(offer_id, post_id):
            raise GigAlreadySubmittedException("Gig is already submitted")
        gig = Gig(offer_id=offer_id, post_id=post_id)

        db.session.add(gig)
        db.session.commit()

        return gig

    def create_submission(self, caption, media):
        if len(self.gig.submissions) > 0 and self.gig.state not in GIG_STATES.REQUIRES_RESUBMIT:
            raise GigAlreadySubmittedException(
                "Can only create a submission when gig is new or requires resubmit"
            )

        validator = ConditionsValidator(self.gig.post.conditions, self.gig.post.start_first_hashtag)
        if self.gig.post.post_type != PostTypes.story:
            try:
                validator.validate(caption)
            except MultipleErrorsError as exc:
                errors = ", ".join(e.message for e in exc.errors)
                raise GigInvalidCaptionException(errors)

        submission = Submission(id=uuid4_str(), gig=self.gig, caption=caption)
        submission.media = [
            Media.from_dict({"order": idx, **m}, submission) for idx, m in enumerate(media)
        ]
        db.session.add(submission)

        self.log.add_event(
            "create_submission",
            {"submission_id": submission.id, "caption": caption, "media": media},
        )

    def update_latest_submission_caption(self, caption):
        if self.gig.submission is None:
            raise GigUpdateCaptionException("Gig has no submission")

        if self.gig.is_verified:
            raise GigUpdateCaptionException("Gig has already been posted")

        validator = ConditionsValidator(self.gig.post.conditions, self.gig.post.start_first_hashtag)
        try:
            validator.validate(caption)
        except MultipleErrorsError as exc:
            errors = ", ".join(e.message for e in exc.errors)
            raise GigInvalidCaptionException(errors)

        self.log.add_event("update_latest_submission_caption", {"caption": caption})

    def report_gig(self, reason, reporter=None):
        if self.gig.state not in [GIG_STATES.REVIEWED, GIG_STATES.APPROVED]:
            raise GigReportException("Can only report reviewed or approved gigs")

        self.log.add_event("report", {"reason": reason})

        if reporter and isinstance(reporter.role, AdvertiserRole):
            slack.brand_reported_gig(self.gig, self.gig.post.campaign.advertiser, reason, reporter)
        else:
            slack.gig_reported(self.gig, self.gig.post.campaign.advertiser, reason, reporter)

    def dismiss_report(self):
        if self.gig.state != GIG_STATES.REPORTED:
            raise GigReportException("Gig is not reported, cannot dismiss report")

        self.log.add_event("dismiss_report")

    def revert_report(self):
        if self.gig.state != GIG_STATES.REPORTED:
            raise GigReportException("Gig is not reported, cannot revert report")

        self.log.add_event("revert_report")

    def request_resubmission(self, reason=None, explanation=None):
        if self.gig.state not in (GIG_STATES.REPORTED, GIG_STATES.SUBMITTED):
            raise GigResubmissionException(
                "Gig has to be submitted or reported to request resubmission"
            )

        if self.gig.instagram_post is not None:
            from takumi.events.instagram_post import InstagramPostLog

            self.log.add_event(
                "unlink_instagram_post", {"instagram_post_id": self.gig.instagram_post.id}
            )
            self.log.add_event("unmark_as_posted")

            ig_post_log = InstagramPostLog(self.gig.instagram_post)
            ig_post_log.add_event("unlink_gig", {"gig_id": self.gig.id})

        if self.gig.instagram_story is not None:
            from takumi.events.instagram_story import InstagramStoryLog

            self.log.add_event(
                "unlink_instagram_story", {"instagram_story_id": self.gig.instagram_story.id}
            )

            ig_story_log = InstagramStoryLog(self.gig.instagram_story)
            ig_story_log.add_event("unlink_gig", {"gig_id": self.gig.id})

        self.log.add_event(
            "request_resubmission", {"reason": reason or "", "explanation": explanation or ""}
        )

    def skip_review_and_approval(self):
        if self.gig.state not in GIG_STATES.SUBMITTED:
            raise GigInvalidStateException("Only submitted gigs can skip review and approval")

        if self.gig.post.requires_review_before_posting:
            raise GigSkipException("Skipping review and approval is not possible for this post")

        self.log.add_event("skip_review_and_approval")

    def set_skip_insights(self, skip_insights):
        self.log.add_event("set_skip_insights", {"skip_insights": skip_insights})

    def mark_as_posted(self, is_posted):
        if is_posted:
            self.log.add_event("mark_as_posted")
        else:
            self.log.add_event("unmark_as_posted")

    def mark_as_verified(self, is_verified):
        if is_verified:
            self.log.add_event("mark_as_verified")
        else:
            self.log.add_event("unmark_as_verified")

    def trigger_transcode_submission(self):
        from takumi.tasks.transcode import transcode_submission

        self.log.add_event("trigger_submission_transcode")
        transcode_submission.delay(submission_id=self.gig.submission.id)
