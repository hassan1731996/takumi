import re
from typing import TYPE_CHECKING, Optional

from facebook_business.api import FacebookRequestError
from sqlalchemy import func

from takumi.extensions import db
from takumi.models import Advertiser, UserAdvertiserAssociation
from takumi.models.user_advertiser_association import create_user_advertiser_association
from takumi.services import Service
from takumi.services.advertiser_industry import AdvertiserIndustryService
from takumi.services.exceptions import (
    AdvertiserDomainBadFormat,
    FacebookException,
    UserNotInAdvertiserException,
)

if TYPE_CHECKING:
    from takumi.models import Region, User  # noqa


class AdvertiserService(Service):
    """
    Represents the business model for Advertiser. This isolates the database
    from the application.
    """

    SUBJECT = Advertiser

    @property
    def advertiser(self) -> Advertiser:
        return self.subject

    # GET
    @staticmethod
    def get_by_id(id: str) -> Optional[Advertiser]:
        return Advertiser.query.get(id)

    @staticmethod
    def get_by_domain(domain: str) -> Optional[Advertiser]:
        return Advertiser.query.filter(Advertiser.domain == domain).one_or_none()

    @staticmethod
    def advertiser_with_domain_exists(domain: str) -> bool:
        return (
            Advertiser.query.filter(func.lower(Advertiser.domain) == func.lower(domain)).count() > 0
        )

    # POST
    @staticmethod
    def create_advertiser(
        created_by: "User",
        unique_ref: str,
        profile_picture: str,
        name: str,
        region: "Region",
        instagram_user: str,
        vat_number: str,
        advertiser_industries_ids: list,
    ) -> Advertiser:
        info = {"instagram": {"user": instagram_user}}

        advertiser = Advertiser(
            profile_picture=profile_picture,
            name=name.strip(),
            domain=unique_ref,
            primary_region_id=region.id,
            vat_number=vat_number,
            regions=[region],
            info=info,
        )

        create_user_advertiser_association(created_by, advertiser, "owner")

        db.session.add(advertiser)
        db.session.commit()

        if advertiser_industries_ids is not None:
            for advertiser_industry_id in advertiser_industries_ids:
                if not AdvertiserIndustryService.check_if_advertiser_has_advertiser_industry(
                    advertiser.id, advertiser_industry_id
                ):
                    AdvertiserIndustryService.add_advertiser_industry_to_advertiser(
                        advertiser.id, advertiser_industry_id
                    )

        return advertiser

    # PUT
    def update_name(self, name: str) -> None:
        self.advertiser.name = name.strip()

    def update_profile_picture(self, profile_picture: str) -> None:
        self.advertiser.profile_picture = profile_picture

    def update_region(self, region_id: str) -> None:
        self.advertiser.primary_region_id = region_id

    def update_influencer_cooldown(self, influencer_cooldown: int) -> None:
        self.advertiser.influencer_cooldown = influencer_cooldown

    def update_archived(self, archived: bool) -> None:
        self.advertiser.archived = archived

    def update_fb_ad_account_id(self, user: "User", fb_ad_account_id: str) -> None:
        if fb_ad_account_id is not None:
            if not user.facebook_account:
                raise FacebookException("Facebook Account not linked")
            try:
                user.facebook_account.ads_api.get_ad_account(f"act_{fb_ad_account_id}")
            except FacebookRequestError:
                raise FacebookException("Invalid Account ID")
            existing_advertiser = Advertiser.query.filter(
                Advertiser.fb_ad_account_id == fb_ad_account_id
            ).one_or_none()
            if existing_advertiser:
                raise FacebookException(f"Ad Account already linked to {existing_advertiser.name}")
        self.advertiser.fb_ad_account_id = fb_ad_account_id

    def update_domain(self, domain: str) -> None:
        if not re.match(r"^[A-Za-z0-9_\-\.]+$", domain):
            raise AdvertiserDomainBadFormat(
                'Brand "domain" (`unique reference`) can not contain special characters'
            )
        self.advertiser.domain = domain

    def update_vat_number(self, vat_number: str) -> None:
        self.advertiser.vat_number = vat_number

    def update_instagram_user(self, instagram_user: str) -> None:
        info = {"instagram": {"user": instagram_user}}
        self.advertiser.info = info

    def remove_user(self, user: "User") -> None:
        if user not in self.advertiser.users:
            raise UserNotInAdvertiserException(
                f"User isn't a part of the '{self.advertiser.name}' brand"
            )

        association = UserAdvertiserAssociation.query.filter(
            UserAdvertiserAssociation.user_id == user.id,
            UserAdvertiserAssociation.advertiser_id == self.advertiser.id,
        ).first()

        db.session.delete(association)
