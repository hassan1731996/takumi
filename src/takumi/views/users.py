from flask import jsonify, request
from flask_login import current_user
from marshmallow import Schema, fields, validate

from core.common.exceptions import APIError

from takumi.auth import influencer_required
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.influencer import (
    CancelScheduledInfluencerDeletion,
    InfluencerAcceptPrivacyPolicy,
    InfluencerAcceptTermsOfService,
    InfluencerRemoveAddress,
    InfluencerSetAddress,
    ScheduleInfluencerDeletion,
    UpdateInfluencerProfile,
)
from takumi.models import Address
from takumi.schemas import InfluencerAddressSchema, SelfInfluencerSchema
from takumi.schemas.signup import validate_birthday
from takumi.services.influencer import InfluencerService, ServiceException
from takumi.templates.template_render import WebPageTemplateRender
from takumi.utils.json import get_valid_json
from takumi.views.blueprint import api


class InfluencerSettingSchema(Schema):
    full_name = fields.String()
    profile_picture = fields.Url()
    gender = fields.String(allow_none=True, validate=validate.OneOf(("male", "female")))
    birthday = fields.Date(validate=validate_birthday)
    email = fields.Email()
    feature_flags = fields.Dict()

    youtube_channel_url = fields.String()
    tiktok_username = fields.String()


@api.route("/self/influencer", methods=["GET"])
@api.route("/users/self", methods=["GET"])
@influencer_required
def influencer_self():
    return SelfInfluencerSchema(context={"user": current_user}), current_user, 200


@api.route("/self/influencer/schedule_delete", methods=["PUT"])
@influencer_required
def influencer_schedule_delete():
    try:
        ScheduleInfluencerDeletion().mutate("info")
    except (MutationException, ServiceException) as e:
        raise APIError(str(e), 400)

    return SelfInfluencerSchema(context={"user": current_user}), current_user, 200


@api.route("/self/influencer/cancel_scheduled_deletion", methods=["PUT"])
@influencer_required
def influencer_cancel_scheduled_deletion():
    try:
        CancelScheduledInfluencerDeletion().mutate("info")
    except (MutationException, ServiceException) as e:
        raise APIError(str(e), 400)

    return SelfInfluencerSchema(context={"user": current_user}), current_user, 200


@api.route("/users/self", methods=["PUT"])  # legacy
@api.route("/self/influencer", methods=["PUT"])
@influencer_required
def influencer_settings():
    form = get_valid_json(InfluencerSettingSchema(), request)

    try:
        UpdateInfluencerProfile().mutate(
            "info",
            full_name=form.get("full_name"),
            profile_picture=form.get("profile_picture"),
            birthday=form.get("birthday"),
            gender=form.get("gender"),
            email=form.get("email"),
            youtube_channel_url=form.get("youtube_channel_url"),
            tiktok_username=form.get("tiktok_username"),
        )
    except (MutationException, ServiceException) as e:
        raise APIError(str(e), 400)

    return SelfInfluencerSchema(context={"user": current_user}), current_user, 200


@api.route("/self/terms/accept", methods=["POST"])
@api.route("/users/self/terms/accept", methods=["POST"])  # legacy
@influencer_required
def accept_terms():
    try:
        InfluencerAcceptTermsOfService().mutate("info")
    except (MutationException, ServiceException) as e:
        raise APIError(str(e), 400)

    return jsonify()


@api.route("/self/privacy/accept", methods=["POST"])
@api.route("/users/self/privacy/accept", methods=["POST"])  # legacy
@influencer_required
def accept_privacy():
    try:
        InfluencerAcceptPrivacyPolicy().mutate("info")
    except (MutationException, ServiceException) as e:
        raise APIError(str(e), 400)

    return jsonify()


@api.route("/self/address", methods=["GET"])
@api.route("/users/self/address", methods=["GET"])  # legacy
@influencer_required
def get_address():
    address = current_user.influencer.address or Address.create_for_influencer(
        current_user.influencer
    )

    return InfluencerAddressSchema(), address, 200


@api.route("/self/address", methods=["DELETE"])
@api.route("/users/self/address", methods=["DELETE"])  # legacy
@influencer_required
def delete_address():

    try:
        InfluencerRemoveAddress().mutate("info")
    except MutationException as e:
        raise APIError(str(e), 400)

    address = Address.create_for_influencer(current_user.influencer)

    return InfluencerAddressSchema(), address, 200


@api.route("/self/address", methods=["PUT"])
@api.route("/users/self/address", methods=["PUT"])  # legacy
@influencer_required
def set_address():
    form = get_valid_json(InfluencerAddressSchema(), request)

    try:
        InfluencerSetAddress().mutate(
            "info",
            form.get("name"),
            form.get("address1"),
            form.get("address2"),
            form.get("city"),
            form.get("postal_code"),
            form.get("country"),
            form.get("state"),
            form.get("phonenumber"),
            form.get("is_pobox"),
        )
    except MutationException as e:
        raise APIError(str(e), 400)

    return InfluencerAddressSchema(), current_user.influencer.address, 200


@api.route("/email/verify/<token>", methods=["GET"])
def verify_email_change(token):
    from takumi.constants import EMAIL_CHANGE_SIGNER
    from takumi.signers import url_signer

    data = url_signer.loads(token, salt=EMAIL_CHANGE_SIGNER)

    influencer = InfluencerService.get_by_id(data["influencer_id"])
    if influencer is None:
        raise APIError("Influencer not found", 403)

    old_email = influencer.user.email
    with InfluencerService(influencer) as service:
        service.update_email(data["email"])

    data = dict(old_email=old_email, new_email=data["email"])
    return WebPageTemplateRender("email_change_success.html", data).render_html()
