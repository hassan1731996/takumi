from takumi.gql import arguments, fields
from takumi.gql.exceptions import QueryException
from takumi.gql.query.influencers.information import InformationParams
from takumi.models import Targeting
from takumi.models.children_targeting import ChildrenTargeting
from takumi.roles import permissions
from takumi.search.influencer import InfluencerSearch
from takumi.services import CampaignService, RegionService


# TODO: should be moved to campaign helpers (not bound to business layer)
def get_campaign_or_404(id):
    campaign = CampaignService.get_by_id(id)
    if campaign is None:
        raise QueryException(f"campaign ({id}) not found")
    return campaign


def get_targeting(  # noqa
    regions,
    gender,
    ages,
    interests,
    max_followers,
    min_followers,
    hair_type_ids,
    hair_colour_categories,
    eye_colour_ids,
    has_glasses,
    languages,
    self_tag_ids,
    min_child_count,
    max_child_count,
    children_ages,
    child_gender,
    has_born_child,
    has_unborn_child,
):
    targeting_tmp = Targeting(ages=ages, interest_ids=interests)
    children_targeting = targeting_tmp.children_targeting = ChildrenTargeting()

    if gender:
        targeting_tmp.gender = None if gender == "all" else gender
    if regions:
        targeting_tmp.regions = RegionService.get_all_by_ids(regions)
    if max_followers is not None:
        targeting_tmp.max_followers = None if max_followers == -1 else max_followers
    if min_followers is not None:
        targeting_tmp.min_followers = None if min_followers == -1 else min_followers

    if hair_type_ids is not None:
        targeting_tmp.hair_type_ids = hair_type_ids
    if hair_colour_categories is not None:
        targeting_tmp.hair_colour_categories = hair_colour_categories
    if eye_colour_ids is not None:
        targeting_tmp.eye_colour_ids = eye_colour_ids
    if has_glasses is not None:
        targeting_tmp.has_glasses = has_glasses
    if languages is not None:
        targeting_tmp.languages = languages
    if self_tag_ids is not None:
        targeting_tmp.self_tag_ids = self_tag_ids

    if children_ages is not None:
        # XXX: Fix in web
        if (
            children_ages
            and len(children_ages) == 2
            and max(children_ages) - min(children_ages) != 1
        ):
            children_ages = list(range(min(children_ages), max(children_ages)))

        children_targeting.ages = children_ages
    if child_gender is not None:
        children_targeting.child_gender = child_gender
    if has_born_child is not None:
        children_targeting.has_born_child = has_born_child
    if has_unborn_child is not None:
        children_targeting.has_unborn_child = has_unborn_child

    return targeting_tmp


def get_eligible(campaign, targeting):
    return InfluencerSearch().filter_campaign_eligibility(campaign, targeting=targeting)


def get_total(campaign):
    return InfluencerSearch().filter_campaign_market(campaign).filter_verified_or_reviewed()


class GenderType(arguments.Enum):
    all = "all"
    male = "male"
    female = "female"


class TargetingEstimateQuery:
    _estimate_args = {
        "campaign_id": arguments.UUID(required=True),
        "regions": arguments.List(arguments.UUID, required=True),
        "gender": GenderType(),
        "ages": arguments.List(arguments.Int),
        "interests": arguments.List(arguments.UUID),
        "max_followers": arguments.Int(),
        "min_followers": arguments.Int(),
        "information": InformationParams(),
    }

    # XXX: drop after removing use of this in takumi-web
    targeting_estimate = fields.Field("TargetingEstimate", **_estimate_args)
    influencer_estimate = fields.Field("TargetingEstimate", **_estimate_args)
    follower_estimate = fields.Field("TargetingEstimate", **_estimate_args)

    @staticmethod
    @permissions.team_member.require()
    def _estimate(
        root,
        info,
        campaign_id,
        regions,
        gender=None,
        ages=None,
        interests=None,
        max_followers=None,
        min_followers=None,
        information=None,
    ):
        campaign = get_campaign_or_404(campaign_id)
        if not information:
            information = {}
        hair_type_ids = information.get("hair_type")
        hair_colour_categories = information.get("hair_colour_category")
        eye_colour_ids = information.get("eye_colour")
        has_glasses = information.get("has_glasses")
        languages = information.get("languages")
        self_tag_ids = information.get("tag_ids")

        min_child_count = information.get("min_child_count")
        max_child_count = information.get("max_child_count")
        children_ages = information.get("children_ages")
        child_gender = information.get("child_gender")
        has_born_child = information.get("has_born_child")
        has_unborn_child = information.get("has_unborn_child")

        targeting_tmp = get_targeting(
            regions,
            gender,
            ages,
            interests,
            max_followers,
            min_followers,
            hair_type_ids,
            hair_colour_categories,
            eye_colour_ids,
            has_glasses,
            languages,
            self_tag_ids,
            min_child_count,
            max_child_count,
            children_ages,
            child_gender,
            has_born_child,
            has_unborn_child,
        )
        eligible = get_eligible(campaign, targeting_tmp)
        total = get_total(campaign)

        def followers():
            eligible.sum("followers", name="reach")
            total.sum("followers", name="reach")
            return {
                "eligible": eligible.aggregations()["reach"]["value"],
                "verified": eligible.filter_verified().aggregations()["reach"]["value"],
                "total": total.aggregations()["reach"]["value"],
            }

        def influencers():
            return {
                "eligible": eligible.count(),
                "verified": eligible.filter_verified().count(),
                "total": total.count(),
            }

        if info.field_name == "followerEstimate":
            return followers()
        elif info.field_name == "influencerEstimate":
            return influencers()
        elif campaign.reward_model == "reach":
            return influencers()
        else:
            return followers()

    resolve_targeting_estimate = _estimate
    resolve_influencer_estimate = _estimate
    resolve_follower_estimate = _estimate
