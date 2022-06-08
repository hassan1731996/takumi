from flask import jsonify, request
from marshmallow import Schema, fields

from takumi.auth import influencer_required
from takumi.gql.mutation.location import UpdateLocation
from takumi.utils.json import get_valid_json

from .blueprint import api


class LocationSchema(Schema):
    lat = fields.String(required=True)
    lon = fields.String(required=True)


@api.route("/location", methods=["POST"])  # legacy
@api.route("/self/location", methods=["POST"])
@influencer_required
def location_update():
    """Update the current location of an influencer

    If the main location has not been set for the influencer, we want to set it
    """
    form = get_valid_json(LocationSchema(), request)

    UpdateLocation().mutate("info", lat=float(form["lat"]), lon=float(form["lon"]))

    return jsonify({}), 200
