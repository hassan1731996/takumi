import re

from flask_login import current_user

from takumi.auth import advertiser_auth
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_advertiser_or_404, get_region_or_404, get_user_or_404
from takumi.roles import permissions
from takumi.services import AdvertiserService
from takumi.tasks.cdn import upload_media_to_cdn
from takumi.utils import uuid4_str


class CreateAdvertiser(Mutation):
    class Arguments:
        name = arguments.String(required=True, strip=True)
        profile_picture = arguments.String(required=True)
        region_id = arguments.UUID(required=True)
        unique_ref = arguments.String(required=True, strip=True)
        instagram_user = arguments.String(strip=True)
        vat_number = arguments.String()
        advertiser_industries_ids = arguments.List(arguments.UUID)

    advertiser = fields.Field("Advertiser")

    @permissions.create_brand.require()
    def mutate(
        root,
        info,
        name,
        profile_picture,
        region_id,
        unique_ref,
        instagram_user=None,
        vat_number=None,
        advertiser_industries_ids=None,
    ):
        if not re.match(r"^[A-Za-z0-9_\-\.]+$", unique_ref):
            raise MutationException(
                'Brand "domain" (`unique reference`) can not contain special characters'
            )

        if AdvertiserService.advertiser_with_domain_exists(unique_ref):
            raise MutationException("Advertiser with this `unique reference` exists")

        region = get_region_or_404(region_id)

        if "imgix" not in profile_picture:
            profile_picture = upload_media_to_cdn(profile_picture, uuid4_str())

        advertiser = AdvertiserService.create_advertiser(
            current_user,
            unique_ref,
            profile_picture,
            name,
            region,
            instagram_user,
            vat_number,
            advertiser_industries_ids,
        )

        return CreateAdvertiser(advertiser=advertiser, ok=True)


class UpdateAdvertiser(Mutation):
    class Arguments:
        id = arguments.UUID(required=True)
        name = arguments.String(strip=True)
        profile_picture = arguments.String()
        region_id = arguments.UUID()
        influencer_cooldown = arguments.Int()
        archived = arguments.Boolean()
        domain = arguments.String(strip=True)
        vat_number = arguments.String(strip=True)
        instagram_user = arguments.String(strip=True)

    advertiser = fields.Field("Advertiser")

    @permissions.create_brand.require()  # Edit?
    def mutate(
        root,
        info,
        id,
        name=None,
        profile_picture=None,
        region_id=None,
        influencer_cooldown=None,
        archived=None,
        domain=None,
        vat_number=None,
        instagram_user=None,
    ):
        advertiser = get_advertiser_or_404(id)

        with AdvertiserService(advertiser) as service:
            if name is not None:
                service.update_name(name)
            if profile_picture is not None:
                service.update_profile_picture(profile_picture)
            if region_id is not None:
                service.update_region(region_id)
            if archived is not None:
                service.update_archived(archived)
            if influencer_cooldown is not None:
                with permissions.set_influencer_cooldown.require():
                    service.update_influencer_cooldown(influencer_cooldown)
            if domain is not None:
                service.update_domain(domain)
            if vat_number is not None:
                service.update_vat_number(vat_number)
            if instagram_user is not None:
                service.update_instagram_user(instagram_user)

        return UpdateAdvertiser(advertiser=advertiser, ok=True)


class RemoveUserFromAdvertiser(Mutation):
    """Remove user from an advertiser"""

    class Arguments:
        id = arguments.UUID(
            required=True, description="ID of the advertiser to remove the user from"
        )
        user_id = arguments.UUID(required=True, description="ID of the user to remove")

    user = fields.Field("User")
    advertiser = fields.Field("Advertiser")

    @permissions.remove_user_from_advertiser.require()
    def mutate(root, info, id, user_id):
        advertiser = get_advertiser_or_404(id)
        user = get_user_or_404(user_id)

        with AdvertiserService(advertiser) as service:
            service.remove_user(user)

        return RemoveUserFromAdvertiser(user=user, advertiser=advertiser, ok=True)


class ConnectFbAdAccountToAdvertiser(Mutation):
    class Arguments:
        id = arguments.UUID(
            required=True, description="ID of the advertiser to connect the facebook ad account to"
        )
        fb_ad_account_id = arguments.String(required=True)

    advertiser = fields.Field("Advertiser")

    @advertiser_auth(key="id", permission=permissions.advertiser_member)
    def mutate(root, info, id, fb_ad_account_id):
        advertiser = get_advertiser_or_404(id)

        with AdvertiserService(advertiser) as service:
            service.update_fb_ad_account_id(current_user, fb_ad_account_id or None)

        return ConnectFbAdAccountToAdvertiser(advertiser=advertiser, ok=True)


class AdvertiserMutation:
    create_advertiser = CreateAdvertiser.Field()
    update_advertiser = UpdateAdvertiser.Field()
    remove_user_from_advertiser = RemoveUserFromAdvertiser.Field()
    connect_fb_ad_account_to_advertiser = ConnectFbAdAccountToAdvertiser.Field()
