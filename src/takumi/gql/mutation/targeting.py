from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.query.influencers.information import InformationParams
from takumi.gql.utils import get_campaign_or_404
from takumi.roles import permissions
from takumi.services import TargetingService


class TargetCampaign(Mutation):
    """Target a campaign"""

    class Arguments:
        id = arguments.UUID(required=True)
        regions = arguments.List(arguments.UUID)
        gender = arguments.String()
        ages = arguments.List(arguments.Int)
        interest_ids = arguments.List(arguments.UUID)
        max_followers = arguments.Int()
        min_followers = arguments.Int()
        verified_only = arguments.Boolean()
        information = InformationParams()

    campaign = fields.Field("Campaign")

    @permissions.edit_campaign.require()
    def mutate(  # noqa: C901
        root,
        info,
        id,
        regions=None,
        gender=None,
        ages=None,
        interest_ids=None,
        max_followers=None,
        min_followers=None,
        verified_only=None,
        information=None,
    ):
        campaign = get_campaign_or_404(id)
        if gender is not None and gender not in ("male", "female", "all"):
            raise MutationException(
                f'`Gender` must be one of "male", "female", or "all". Received "{gender}"',
                412,
            )

        if information is None:
            information = {}

        hair_type_ids = sorted(information.get("hair_type") or [])
        hair_colour_categories = sorted(information.get("hair_colour_category") or [])
        eye_colour_ids = sorted(information.get("eye_colour") or [])
        has_glasses = information.get("has_glasses")
        languages = sorted(information.get("languages") or [])
        self_tag_ids = sorted(information.get("tag_ids") or [])

        min_child_count = information.get("min_child_count")
        min_child_count = information.get("min_child_count")
        max_child_count = information.get("max_child_count")
        children_ages = information.get("children_ages")
        child_gender = information.get("child_gender")
        has_born_child = information.get("has_born_child")
        has_unborn_child = information.get("has_unborn_child")

        with TargetingService(campaign.targeting) as service:
            if regions is not None and campaign.targeting.regions != regions:
                service.update_regions(regions)
            if gender is not None:
                service.update_gender(gender)
            if ages is not None:
                service.update_ages(ages)

            if min_followers is not None or max_followers is not None:
                # Client sends -1 to clear values
                if min_followers == -1:
                    min_followers = None
                if max_followers == -1:
                    max_followers = None
                service.update_followers(min_followers=min_followers, max_followers=max_followers)

            if verified_only is not None:
                service.update_verified_only(verified_only)
            service.update_interests(interest_ids)

            if campaign.targeting.hair_type_ids != hair_type_ids:
                service.update_hair_type_ids(hair_type_ids)
            if campaign.targeting.hair_colour_categories != hair_colour_categories:
                service.update_hair_colour_categories(hair_colour_categories)
            if campaign.targeting.eye_colour_ids != eye_colour_ids:
                service.update_eye_colour_ids(eye_colour_ids)
            if campaign.targeting.has_glasses != has_glasses:
                service.update_has_glasses(has_glasses)
            if campaign.targeting.languages != languages:
                service.update_languages(languages)
            if campaign.targeting.self_tag_ids != self_tag_ids:
                service.update_self_tag_ids(self_tag_ids)

            service.update_children_targeting(
                has_born_child,
                has_unborn_child,
                min_child_count,
                max_child_count,
                children_ages,
                child_gender,
            )

        return TargetCampaign(campaign=campaign, ok=True)


class TargetingMutation:
    target_campaign = TargetCampaign.Field()
