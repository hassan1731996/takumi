import json

from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.history.interface import HistoryInterface
from takumi.models import Image, Submission, Video
from takumi.utils import uuid4_str

# Real events


class GigReviewEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)


class GigApproveEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)


class GigResubmissionRequestEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)

    reason = fields.String(resolver=fields.deep_source_resolver("event.reason"))
    explanation = fields.String(resolver=fields.deep_source_resolver("event.explanation"))


class CreateSubmissionEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)

    submission = fields.Field("Submission")

    def resolve_submission(event, info):
        class Submission:
            def __init__(self, created, caption, media):
                self.id = uuid4_str()
                self.created = created
                self.caption = caption

                self.media = [self.to_temp_media(m) for m in media]

            def to_temp_media(self, media):
                args = {
                    "id": uuid4_str(),
                    "url": media["url"],
                    "order": media.get("order"),
                    "owner_type": "submission",
                    "owner_id": uuid4_str(),
                }
                if media["type"] == "video":
                    return Video(**args, thumbnail=media.get("thumbail"))
                else:
                    return Image(**args)

        return Submission(event.created, event.event["caption"], json.loads(event.event["media"]))


class LegacyCreateInstagramPostEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)

    ig_post_id = fields.String(resolver=fields.deep_source_resolver("event.ig_post_id"))
    link = fields.String(resolver=fields.deep_source_resolver("event.link"))
    comments = fields.Int(resolver=fields.deep_source_resolver("event.comments"))
    likes = fields.Int(resolver=fields.deep_source_resolver("event.likes"))
    posted = fields.DateTime(resolver=fields.deep_source_resolver("event.posted"))


class UpdateCaptionEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)

    submission = fields.Field("Submission")

    def resolve_submission(event, info):
        if "submisson_id" in event.event:
            return Submission.query.get(event.event["submission_id"])
        return event.gig.submission


class ReportEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)

    reason = fields.String(resolver=fields.deep_source_resolver("event.reason"))
    explanation = fields.String(resolver=fields.deep_source_resolver("event.explanation"))


class DismissReportEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)


class RejectGigEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)

    reason = fields.String(resolver=fields.deep_source_resolver("event.reason"))


# Custom events


class ReserveEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)


class PostedToInstagramFeedEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)

    link = fields.String(resolver=fields.deep_source_resolver("event.link"))


class PostedToInstagramStoryEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)


class OfferClaimedEvent(ObjectType):
    class Meta:
        interfaces = (HistoryInterface,)

    payment = fields.Field("Payment", resolver=fields.deep_source_resolver("event.payment"))


history_items = {
    "approve": GigApproveEvent,
    "request_resubmission": GigResubmissionRequestEvent,
    "review": GigReviewEvent,
    "legacy_create_submission": CreateSubmissionEvent,
    "create_submission": CreateSubmissionEvent,
    "legacy_create_instagram_post": LegacyCreateInstagramPostEvent,
    "update_latest_submission_caption": UpdateCaptionEvent,
    "report": ReportEvent,
    "reserve": ReserveEvent,
    "reject": RejectGigEvent,
    "dismiss_report": DismissReportEvent,
    "posted_to_instagram_feed": PostedToInstagramFeedEvent,
    "posted_to_instagram_story": PostedToInstagramStoryEvent,
    "offer_claimed": OfferClaimedEvent,
}
