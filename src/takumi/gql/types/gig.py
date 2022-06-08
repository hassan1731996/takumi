from flask_login import current_user
from graphene import ObjectType

from takumi.gql import fields
from takumi.gql.history.interface import HistoryInterface
from takumi.gql.relay import Connection, Node
from takumi.gql.utils import influencer_post_step
from takumi.models import Currency
from takumi.models.gig import STATES as GIG_STATES
from takumi.roles import permissions
from takumi.services import GigService


class GigTimelineField(ObjectType):
    external_review_deadline = fields.DateTime(
        resolver=fields.deep_source_resolver("schedule.external_review_deadline")
    )
    internal_review_deadline = fields.ManageInfluencersField(
        fields.DateTime, resolver=fields.deep_source_resolver("schedule.internal_review_deadline")
    )


class InsightStatus(fields.Enum):
    not_set = "not_set"
    missing = "missing"
    submitted = "submitted"
    approved = "approved"


class Gig(ObjectType):
    class Meta:
        interfaces = (Node,)

    state = fields.String()
    created = fields.DateTime()
    report_reason = fields.String()
    reporter = fields.ManageInfluencersField("User")
    reject_reason = fields.String()

    reward = fields.ManageInfluencersField(
        "Currency", deprecation_reason="Reward is for the whole campaign. Use Offer.reward"
    )

    influencer = fields.Field(
        "Influencer", resolver=fields.deep_source_resolver("offer.influencer")
    )

    reviewer = fields.ManageInfluencersField("User")
    review_date = fields.ManageInfluencersField(fields.DateTime)
    approver = fields.ManageInfluencersField("User")
    approve_date = fields.ManageInfluencersField(fields.DateTime)

    post = fields.Field("Post")
    offer = fields.Field("Offer")
    submission = fields.Field("Submission")

    resubmit_reason = fields.String()
    resubmit_explanation = fields.String()

    is_passed_review_period = fields.Boolean()

    can_be_reported = fields.AdvertiserField(fields.Boolean)
    is_posted = fields.Boolean(source="is_verified")  # XXX: Temporarily while switching web over
    is_verified = fields.Boolean()

    instagram_content = fields.Field("InstagramContentInterface")
    instagram_post = fields.Field(
        "InstagramPost",
        deprecation_reason="Gigs can have either story or instagram posts. Use InstagramContentInterface",
    )
    tiktok_post = fields.Field("TiktokPost")
    insight = fields.Field("InsightInterface")
    skip_insights = fields.ManageInfluencersField(fields.Boolean)
    is_missing_insights = fields.ManageInfluencersField(fields.Boolean)
    has_valid_insights = fields.ManageInfluencersField(fields.Boolean)
    influencer_step = fields.ManageInfluencersField(fields.String)

    insight_status = fields.ManageInfluencersField(InsightStatus)

    history = fields.ManageInfluencersField(fields.List(HistoryInterface))

    def resolve_insight_status(gig, info):
        if not (gig.requires_insights and gig.is_passed_review_period):
            return InsightStatus.not_set
        elif gig.is_missing_insights:
            return InsightStatus.missing
        elif gig.has_valid_insights:
            return InsightStatus.approved
        else:
            return InsightStatus.submitted

    def resolve_insight(gig, info):
        if (
            permissions.manage_influencers.can()
            or getattr(current_user, "influencer", None) == gig.offer.influencer
        ):
            return gig.insight

    def resolve_instagram_content(gig, info):
        if gig.instagram_post is not None:
            return gig.instagram_post

        if gig.instagram_story is not None:
            return gig.instagram_story

        if gig.tiktok_post is not None:
            return gig.tiktok_post

        return None

    def resolve_history(gig, info):
        from takumi.gql.history.gig import history_items
        from takumi.models import GigEvent

        q = GigEvent.query.filter(GigEvent.gig_id == gig.id, GigEvent.type.in_(history_items))
        if not gig.offer.campaign.brand_safety:
            q = q.filter(GigEvent.type != "approve")
        events = q.all()

        user = gig.offer.influencer.user

        extra_events = []

        extra_events.append(
            GigEvent(
                type="reserve", created=gig.offer.accepted, creator_user=gig.offer.influencer.user
            )
        )
        if gig.is_verified:
            if gig.instagram_post:
                extra_events.append(
                    GigEvent(
                        type="posted_to_instagram_feed",
                        created=gig.instagram_post.posted,
                        creator_user=user,
                        event={"link": gig.instagram_post.link},
                    )
                )
            elif gig.instagram_story and gig.instagram_story.has_marked_frames:
                extra_events.append(
                    GigEvent(
                        type="posted_to_instagram_story",
                        created=gig.instagram_story.posted,
                        creator_user=user,
                    )
                )
        if gig.offer.claimed is not None:
            extra_events.append(
                GigEvent(
                    type="offer_claimed",
                    created=gig.offer.claimed,
                    creator_user=user,
                    event={"payment": gig.offer.payment},
                )
            )

        return sorted([*events, *extra_events], key=lambda event: event.created, reverse=True)

    def resolve_resubmit_reason(gig, info):
        """Return the current _or_ previous gigs resubmit reason

        If the current gig doesn't have a report reason, we look for older gigs
        until we either find a report reason or there is none.

        This is a hacky way of exposing a "report reason history", until we
        have a better way of structuring the data for the client.
        """
        if gig.state == GIG_STATES.REQUIRES_RESUBMIT:
            return gig.resubmit_reason

        resubmit_gig = GigService.get_latest_influencer_require_resubmit_gig_of_a_post(
            gig.offer.influencer.id, gig.post.id
        )

        if resubmit_gig is not None:
            return resubmit_gig.resubmit_reason

        return None

    def resolve_resubmit_explanation(gig, info):
        if gig.state == GIG_STATES.REQUIRES_RESUBMIT:
            return gig.resubmit_explanation

        resubmit_gig = GigService.get_latest_influencer_require_resubmit_gig_of_a_post(
            gig.offer.influencer.id, gig.post.id
        )

        if resubmit_gig is not None:
            return resubmit_gig.resubmit_explanation

        return None

    def resolve_can_be_reported(gig, info):
        if gig.state in [GIG_STATES.REVIEWED, GIG_STATES.APPROVED]:
            return not gig.is_passed_review_period or permissions.report_after_review_period.can()
        return False

    def resolve_reward(gig, info):
        # Deprecated
        offer = gig.offer

        post_count = len(offer.campaign.posts)
        reward = offer.reward

        currency = offer.campaign.market.currency
        return Currency(amount=(reward / post_count), currency=currency)

    def resolve_influencer_step(gig, info):
        return influencer_post_step(post=gig.post, influencer=gig.offer.influencer, gig=gig)


class GigPagination(ObjectType):
    previous = fields.UUID()
    next = fields.UUID()


class GigConnection(Connection):
    class Meta:
        node = Gig


class GigForPostConnection(Connection):
    class Meta:
        node = Gig
