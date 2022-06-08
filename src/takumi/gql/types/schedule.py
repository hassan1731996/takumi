from graphene import ObjectType

from takumi.gql import fields


class Schedule(ObjectType):
    # Influencer sees these dates
    submission_deadline = fields.DateTime()
    post_deadline = fields.DateTime()
    post_to_instagram_deadline = fields.DateTime(
        deprecation_reason="Use postDeadline", source="post_deadline"
    )
    post_claimable_deadline = fields.DateTime()

    # These dates are only for the schedule visualzer
    internal_review_deadline = fields.DateTime()
    external_review_deadline = fields.DateTime()

    # These dates are for recommending a submission deadline
    suggested_earliest_submission_deadline = fields.DateTime()
    suggested_latest_submission_deadline = fields.DateTime()
