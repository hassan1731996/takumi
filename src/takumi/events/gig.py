import json

from takumi.events import Event, EventApplicationException, TableLog
from takumi.models import GigEvent
from takumi.models.gig import STATES


class ValueMissingException(EventApplicationException):
    pass


##################
# State changers #
##################


class RequestResubmission(Event):
    start_state = (STATES.SUBMITTED, STATES.REPORTED)
    end_state = STATES.REQUIRES_RESUBMIT

    def apply(self, gig):
        gig.resubmit_reason = self.properties["reason"]
        gig.resubmit_explanation = self.properties["explanation"]
        gig.approver = None
        gig.reviewer = None


class DismissGigReport(Event):
    start_state = STATES.REPORTED
    end_state = STATES.APPROVED

    def apply(self, gig):
        pass


class RevertReport(Event):
    start_state = STATES.REPORTED
    end_state = STATES.REVIEWED

    def apply(self, gig):
        pass


class ReportGig(Event):
    start_state = (STATES.REVIEWED, STATES.APPROVED)
    end_state = STATES.REPORTED

    def apply(self, gig):
        gig.report_reason = self.properties["reason"]


class RejectGig(Event):
    start_state = (STATES.SUBMITTED, STATES.REPORTED)
    end_state = STATES.REJECTED

    def apply(self, gig):
        gig.reject_reason = self.properties["reason"]


################
# Other events #
################


class ReviewGig(Event):
    start_state = STATES.SUBMITTED
    end_state = STATES.REVIEWED

    def apply(self, gig):
        gig.reviewer_id = self.properties["reviewer_id"]
        gig.review_date = self.properties["review_date"]


class ApproveGig(Event):
    start_state = STATES.REVIEWED
    end_state = STATES.APPROVED

    def apply(self, gig):
        gig.approver_id = self.properties["approver_id"]
        gig.approve_date = self.properties["approve_date"]


class SkipReviewAndApproval(Event):
    start_state = STATES.SUBMITTED
    end_state = STATES.APPROVED

    def apply(self, gig):
        pass


class ReviewApprovedGig(Event):
    start_state = STATES.APPROVED

    def apply(self, gig):
        gig.reviewer_id = self.properties["reviewer_id"]


class UnlinkInstagramPost(Event):
    def apply(self, gig):
        gig.is_verified = False


class UnlinkTiktokPost(Event):
    def apply(self, gig):
        gig.is_verified = False


class CreateSubmission(Event):
    start_state = (STATES.REQUIRES_RESUBMIT, STATES.SUBMITTED)
    end_state = STATES.SUBMITTED

    def apply(self, gig):
        # Clear out resubmit info when creating submit
        gig.resubmit_reason = None
        gig.resubmit_explanation = None
        # Json dump the media to store it
        self.properties["media"] = json.dumps(self.properties["media"])


class UnlinkInstagramStory(Event):
    def apply(self, gig):
        gig.is_posted = False
        gig.is_verified = False


class MarkAsPosted(Event):
    def apply(self, gig):
        gig.is_posted = True


class UnmarkAsPosted(Event):
    def apply(self, gig):
        gig.is_posted = False


class MarkAsVerified(Event):
    def apply(self, gig):
        gig.is_posted = True
        gig.is_verified = True


class UnmarkAsVerified(Event):
    def apply(self, gig):
        gig.is_verified = False


class SetSkipInsights(Event):
    def apply(self, gig):
        gig.skip_insights = self.properties["skip_insights"]


class UpdateLatestSubmissionCaption(Event):
    def apply(self, gig):
        gig.submission.caption = self.properties["caption"]
        self.properties["submission_id"] = gig.submission.id


class TriggerSubmissionTranscode(Event):
    def apply(self, gig):
        gig.submission.transcoded = True


class GigLog(TableLog):
    event_model = GigEvent
    relation = "gig"
    type_map = {
        # State changers
        "reject": RejectGig,
        "report": ReportGig,
        "dismiss_report": DismissGigReport,
        "revert_report": RevertReport,
        "request_resubmission": RequestResubmission,
        # Other events
        "approve": ApproveGig,
        "create_submission": CreateSubmission,
        "mark_as_posted": MarkAsPosted,
        "mark_as_verified": MarkAsVerified,
        "review": ReviewGig,
        "review_approved_gig": ReviewApprovedGig,
        "set_skip_insights": SetSkipInsights,
        "skip_review_and_approval": SkipReviewAndApproval,
        "unlink_instagram_post": UnlinkInstagramPost,
        "unlink_tiktok_post": UnlinkTiktokPost,
        "unlink_instagram_story": UnlinkInstagramStory,
        "unmark_as_posted": UnmarkAsPosted,
        "unmark_as_verified": UnmarkAsVerified,
        "update_latest_submission_caption": UpdateLatestSubmissionCaption,
        "trigger_submission_transcode": TriggerSubmissionTranscode,
    }
