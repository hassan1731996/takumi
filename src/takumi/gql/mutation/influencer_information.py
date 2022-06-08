from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import min_version_required
from takumi.models import Influencer
from takumi.models.influencer_information import InfluencerChild
from takumi.roles import permissions
from takumi.services import InfluencerService


class Gender(arguments.Enum):
    male = "male"
    female = "female"
    unknown = "unknown"


class EyeColour(arguments.Enum):
    green = "green"
    blue = "blue"


class ChildrenInput(arguments.InputObjectType):
    id = arguments.UUID()
    gender = Gender(required=True)
    birthday = arguments.Date()


class AccountType(arguments.Enum):
    normal = "normal"
    business = "business"
    creator = "creator"


class AppearanceInput(arguments.InputObjectType):
    hair_colour = arguments.UUID()
    eye_colour = arguments.UUID()
    hair_type = arguments.UUID()
    glasses = arguments.Boolean()


def get_influencer(username=None):
    if username is None:
        influencer = current_user.influencer
    else:
        influencer = Influencer.by_username(username)
    if influencer is not None and (
        current_user.influencer == influencer or current_user.role_name == "developer"
    ):
        return influencer
    raise MutationException("Influencer ({}) not found".format(username or ""))


class SetInfluencerInformation(Mutation):
    """Set tags on an influencer"""

    class Arguments:
        id = arguments.UUID()
        username = arguments.String()
        tags = arguments.List(arguments.UUID)
        children = arguments.List(ChildrenInput)
        languages = arguments.List(arguments.String)
        appearance = AppearanceInput()
        account_type = AccountType()

    influencer = fields.Field("Influencer")

    @permissions.influencer.require()
    @min_version_required("5.28.5")
    def mutate(
        root,
        info,
        id=None,
        username=None,
        tags=None,
        children=None,
        languages=None,
        appearance=None,
        account_type=None,
    ):
        influencer = get_influencer(id or username)
        if appearance is None:
            appearance = {}
        if children is not None:
            children_models = []
            for child_dict in children:
                child_id = child_dict.pop("id", None)
                if child_id:
                    child = InfluencerChild.query.get(child_id)
                else:
                    child = InfluencerChild()
                for key in child_dict:
                    setattr(child, key, child_dict[key])
                children_models.append(child)
            children = children_models
        with InfluencerService(influencer) as srv:
            # Before app version 5.19.11 the glasses boolean was flipped in the
            # app, so for any request that submits with a version before that,
            # we have to flip the boolean before applying it.
            client_version = info.context.get("client_version")
            glasses = appearance.get("glasses")
            if client_version is not None and client_version < (5, 19, 11) and glasses is not None:
                glasses = not glasses

            srv.set_influencer_information(
                tag_ids=tags,
                children=children,
                account_type=account_type,
                languages=languages,
                hair_colour_id=appearance.get("hair_colour"),
                hair_type_id=appearance.get("hair_type"),
                eye_colour_id=appearance.get("eye_colour"),
                glasses=glasses,
            )

        return SetInfluencerInformation(influencer=influencer, ok=True)


class InfluencerInformationMutation:
    set_influencer_information = SetInfluencerInformation.Field()
