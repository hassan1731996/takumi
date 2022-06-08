from takumi.gql import arguments, fields
from takumi.gql.exceptions import GraphQLException
from takumi.gql.interfaces import InstagramUserInterface
from takumi.roles import permissions

from .influencer import InfluencerQuery
from .instagram import InstagramQuery


class ProfileQuery:
    profile = fields.Field(InstagramUserInterface, username=arguments.String(), id=arguments.UUID())

    @permissions.public.require()
    def resolve_profile(root, info, username=None, id=None):
        if not any([username, id]):
            raise GraphQLException(
                "Can not resolve an influencer without either `id` or `username`"
            )
        profile = InfluencerQuery().resolve_influencer(info, username, id)

        if not profile:
            profile = InstagramQuery().resolve_instagram_user(info, username)

        return profile
