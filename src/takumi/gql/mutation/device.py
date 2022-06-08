import datetime as dt
from typing import Optional

from flask import g
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.gql.mutation.base import Mutation
from takumi.location import update_influencer_location_by_ip
from takumi.models import Influencer
from takumi.roles import permissions
from takumi.services import DeviceService


def _track_device(device, state):
    payload = {"state": state}

    if device is not None:
        payload.update(
            {
                "device_id": getattr(device, "id", None),
                "model": device.device_model,
                "os_version": device.os_version,
                "build_version": device.build_version,
            }
        )


class RegisterDevice(Mutation):
    class Arguments:
        token = arguments.String(required=True)
        model = arguments.String()
        os_version = arguments.String()
        build_version = arguments.String()
        locale = arguments.String()
        timezone = arguments.String()

    new = fields.Boolean()

    @permissions.influencer.require()
    def mutate(
        root,
        info,
        token: str,
        model: Optional[str] = None,
        os_version: Optional[str] = None,
        build_version: Optional[str] = None,
        locale: Optional[str] = None,
        timezone: Optional[str] = None,
    ):
        if g.is_developer:
            return RegisterDevice(ok=True)

        influencer: Influencer = current_user.influencer

        update_influencer_location_by_ip(influencer)

        device = current_user.device

        existing_device = DeviceService.get_by_token(token)
        if existing_device and existing_device != device:
            with DeviceService(existing_device) as service:
                service.update_device_token(None)
                service.update_active(False)

        if device:
            new = False
        else:
            new = True
            try:
                current_user.device = device = DeviceService.create_device(current_user, token)
            except IntegrityError:
                db.session.rollback()
                return RegisterDevice(ok=True, new=False)

        with DeviceService(device) as service:
            if token != device.device_token:
                service.update_device_token(token)
            if model != device.device_model:
                service.update_device_model(token)
            if os_version != device.os_version:
                service.update_os_version(os_version)
            if build_version != device.build_version:
                service.update_build_version(build_version)
            if not device.active:
                service.update_active(True)

        if locale:
            current_user.locale = locale.replace("-", "_")

        if timezone:
            current_user.timezone = timezone

        device.last_used = dt.datetime.now(dt.timezone.utc)

        try:
            db.session.add(device)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return RegisterDevice(ok=True, new=False)
        return RegisterDevice(ok=True, new=new)


class DeviceMutation:
    register_device = RegisterDevice.Field()
