from flask_login import current_user

from takumi.emails import ResubmitInsightsEmail
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_gig_or_404, get_insight_media_or_404, get_insight_or_404
from takumi.i18n import locale_context
from takumi.roles import permissions
from takumi.services import InsightService
from takumi.tasks.ocr import analyse_post_insight


class SubmitInsight(Mutation):
    """Submit an insight for a gig"""

    class Arguments:
        insight_urls = arguments.List(arguments.Url, required=True)
        gig_id = arguments.UUID(required=True)

    insight = fields.Field("InsightInterface")

    @permissions.public.require()
    def mutate(root, info, insight_urls, gig_id):
        gig = get_gig_or_404(gig_id)

        if not permissions.campaign_manager.can():
            if getattr(current_user, "influencer") != gig.offer.influencer:
                raise MutationException(f"Gig ({gig_id}) not found")

        if gig.insight is None:
            insight = InsightService.create(gig)
        else:
            insight = gig.insight

        with InsightService(insight) as service:
            service.add_media(insight_urls=insight_urls)

        return SubmitInsight(ok=True, insight=insight)


class RemoveInsightMedia(Mutation):
    """Remove a media from an insight"""

    class Arguments:
        id = arguments.UUID(required=True, description="The media ID")

    insight = fields.Field("InsightInterface")

    @permissions.public.require()
    def mutate(root, info, id):
        media = get_insight_media_or_404(id)
        insight = media.insight

        if not permissions.manage_influencers.can():
            if getattr(current_user, "influencer") != insight.gig.offer.influencer:
                raise Mutation(f"Media ({id}) not found")

        with InsightService(media.insight) as service:
            service.remove_media(id)

        return RemoveInsightMedia(ok=True, insight=insight)


class UpdatePostInsight(Mutation):
    """Update post insight metadata"""

    class Arguments:
        id = arguments.UUID(required=True, description="The insight ID")

        processed = arguments.Boolean(description="Whether the insight has been processed")

        reach = arguments.Int(description="Accounts reached with the instagram post")
        non_followers_reach = arguments.Float(
            description="Ration of non-follower accounts reached with the instagram post"
        )

        likes = arguments.Int(description="Number of likes on the instagram post")
        comments = arguments.Int(description="Number of comments on the instagram post")
        shares = arguments.Int(description="Number of shares on the instagram post")
        bookmarks = arguments.Int(
            description="Number of times the instagram post was added to bookmarks"
        )

        profile_visits = arguments.Int(
            description="Number of profile visits from the instagram post"
        )
        replies = arguments.Int(description="Number of replies to the instagram post")
        website_clicks = arguments.Int(
            description="Number of website clicks from the instagram post"
        )
        calls = arguments.Int(description="Number of calls from the instagram post")
        emails = arguments.Int(description="Number of emails from the instagram post")
        get_directions = arguments.Int(
            description="Number of 'get directions' from the instagram post"
        )

        follows = arguments.Int(description="Number of follows the instagram post generated")

        from_hashtags_impressions = arguments.Int(
            description="Impressions from hashtags generated with the instagram post"
        )
        from_home_impressions = arguments.Int(
            description="Impressions from home screen generated with the instagram post"
        )
        from_explore_impressions = arguments.Int(
            description="Impressions from explore screen generated with the instagram post"
        )
        from_profile_impressions = arguments.Int(
            description="Interactions from profile done with the instagram post"
        )
        from_other_impressions = arguments.Int(
            description="Interactions from other source done with the instagram post"
        )
        from_location_impressions = arguments.Int(
            description="Interactions from location done with the instagram post"
        )

    insight = fields.Field("InsightInterface")

    @permissions.manage_influencers.require()
    def mutate(root, info, id, **args):
        insight = get_insight_or_404(id)

        if "non_followers_reach" in args:
            # Clients send non followers reach as whole percentage, server stores it in a float
            args["non_followers_reach"] /= 100

        with InsightService(insight) as service:
            service.update_post_insight(args)

        # Approve in separate transaction so the approve event is after any updates
        with InsightService(insight) as service:
            service.approve()

        return UpdatePostInsight(ok=True, insight=insight)


class UpdateStoryInsight(Mutation):
    """Update story insight metadata"""

    class Arguments:
        id = arguments.UUID(required=True, description="The insight ID")

        processed = arguments.Boolean(description="Whether the insight has been processed")

        reach = arguments.Int(description="Accounts reached with the instagram story")

        views = arguments.Int(description="Number of views on the instagram story")

        shares = arguments.Int(description="Number of shares of the story")

        replies = arguments.Int(description="Number of replies interacted on the instagram story")

        impressions = arguments.Int(description="Impressions generated with the instagram story")

        link_clicks = arguments.Int(
            description="Number of link clicks performed on the instagram story"
        )
        sticker_taps = arguments.Int(
            description="Number of sticker taps performed on the instagram story"
        )

        profile_visits = arguments.Int(
            description="Number of profile visits from the instagram post"
        )
        follows = arguments.Int(description="Number of follows the instagram post generated")

        back_navigations = arguments.Int(
            description="Number of back navigations performed on the instagram story"
        )
        forward_navigations = arguments.Int(
            description="Number of forward navigations performed on the instagram story"
        )
        next_story_navigations = arguments.Int(
            description="Number of next story navigations performed on the instagram story"
        )
        exited_navigations = arguments.Int(
            description="Number of exited navigations performed on the instagram story"
        )
        website_clicks = arguments.Int(
            description="Number of website clicks from the instagram story"
        )
        emails = arguments.Int(description="Number of emails from the instagram story")

    insight = fields.Field("InsightInterface")

    @permissions.manage_influencers.require()
    def mutate(root, info, id, **args):
        insight = get_insight_or_404(id)

        with InsightService(insight) as service:
            service.update_story_insight(args)

        # Approve in separate transaction so the approve event is after any updates
        with InsightService(insight) as service:
            service.approve()

        return UpdateStoryInsight(ok=True, insight=insight)


class RequestInsightResubmission(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="The insight ID")
        reason = arguments.String(required=True, description="The reason for the resubmit request")

    insight = fields.Field("InsightInterface")

    @permissions.manage_influencers.require()
    def mutate(root, info, id, reason):
        insight = get_insight_or_404(id)

        with InsightService(insight) as service:
            service.request_resubmission(reason)

        with locale_context(insight.gig.offer.influencer.user):
            ResubmitInsightsEmail(
                {"reason": reason, "campaign_name": insight.gig.offer.campaign.name}
            ).send(insight.gig.offer.influencer.email)

        return RequestInsightResubmission(ok=True, insight=insight)


class TriggerInsightOCR(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="The insight ID")

    insight = fields.Field("InsightInterface")

    @permissions.manage_influencers.require()
    def mutate(root, info, id):
        insight = get_insight_or_404(id)

        analyse_post_insight.delay(id)

        return TriggerInsightOCR(ok=True, insight=insight)


class InsightMutation:
    remove_insight_media = RemoveInsightMedia.Field()
    submit_insight = SubmitInsight.Field()
    update_post_insight = UpdatePostInsight.Field()
    update_story_insight = UpdateStoryInsight.Field()
    request_insight_resubmission = RequestInsightResubmission.Field()
    trigger_insight_ocr = TriggerInsightOCR.Field()
