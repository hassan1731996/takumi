from flask import g, jsonify, request
from flask_login import login_required
from marshmallow import Schema, fields, pre_load

from takumi.gql.mutation.device import RegisterDevice
from takumi.utils.json import get_valid_json

from .blueprint import api


class CreateMobileDeviceSchema(Schema):
    id = fields.UUID(required=True)
    token = fields.String(required=True)
    model = fields.String()
    os_version = fields.String()
    build_version = fields.String()
    locale = fields.String()
    timezone = fields.String()

    @pre_load
    def pre_load(self, item):
        if isinstance(item.get("os_version"), int):
            item["os_version"] = str(item["os_version"])
        return item


@api.route("/devices", methods=["POST"])  # noqa
@api.route("/self/devices", methods=["POST"])
@login_required
def create_device():
    if g.is_developer:
        return jsonify({}), 200
    # send a request to here everytime we login/signup

    form = get_valid_json(CreateMobileDeviceSchema(), request)
    token = form["token"]
    model = form.get("model")
    os_version = form.get("os_version")
    build_version = form.get("build_version")
    locale = form.get("locale")
    timezone = form.get("timezone")

    response = RegisterDevice().mutate(
        "info",
        token=token,
        model=model,
        os_version=os_version,
        build_version=build_version,
        locale=locale,
        timezone=timezone,
    )

    return jsonify({}), 201 if response.new else 200
