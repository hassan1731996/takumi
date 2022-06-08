from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_influencer_or_404
from takumi.models.audience_insight import STATES as AUDIENCE_STATES
from takumi.roles import permissions
from takumi.services import AudienceInsightService
from takumi.tasks.ocr import analyse_audience_insight


class SubmitAudienceInsight(Mutation):
    class Arguments:
        username = arguments.String()
        top_locations = arguments.Url(required=True)
        ages_men = arguments.Url(required=True)
        ages_women = arguments.Url(required=True)
        gender = arguments.Url(required=True)

    insight = fields.Field("AudienceInsight")

    @permissions.public.require()
    def mutate(root, info, top_locations, ages_men, ages_women, gender, username=None):
        if username:
            if permissions.manage_influencers.can():
                influencer = get_influencer_or_404(username)
            else:
                raise MutationException("Influencer not found")
        else:
            influencer = current_user.influencer

        if influencer is None:
            raise MutationException("Influencer not found")

        existing = influencer.audience_insight
        if existing and existing.state == AUDIENCE_STATES.SUBMITTED:
            raise MutationException("Audience insights have already been submitted")

        insight = AudienceInsightService.create(
            influencer,
            top_locations_url=top_locations,
            ages_men_url=ages_men,
            ages_women_url=ages_women,
            gender_url=gender,
        )

        analyse_audience_insight.delay(insight.id)

        return SubmitAudienceInsight(ok=True, insight=insight)


class AudienceInsightMutation:
    submit_audience_insight = SubmitAudienceInsight.Field()
