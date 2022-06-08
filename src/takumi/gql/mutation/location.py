from flask import g
from flask_login import current_user

from takumi.gql import arguments
from takumi.gql.mutation.base import Mutation
from takumi.location import update_influencer_location_with_coordinates
from takumi.roles import permissions


class UpdateLocation(Mutation):
    class Arguments:
        lat = arguments.Float(
            required=True,
            description="Location latitude. Any precision above 2 places will be discarded",
        )
        lon = arguments.Float(
            required=True,
            description="Location longitude. Any precision above 2 places will be discarded",
        )

    @permissions.influencer.require()
    def mutate(root, info, lat: float, lon: float) -> "UpdateLocation":
        if getattr(g, "is_developer", False):
            return UpdateLocation(ok=True)

        influencer = current_user.influencer

        # Discard above 2 precision
        lat = round(lat, 2)
        lon = round(lon, 2)

        update_influencer_location_with_coordinates(influencer, lat=lat, lon=lon)

        return UpdateLocation(ok=True)


class LocationMutation:
    update_location = UpdateLocation.Field()
