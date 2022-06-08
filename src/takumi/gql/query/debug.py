from typing import Dict, Optional

from takumi.gql import arguments, fields
from takumi.gql.utils import get_influencer_or_404
from takumi.models import (
    Device,
    FacebookAccount,
    FacebookPage,
    Influencer,
    InstagramAccount,
    TikTokAccount,
    User,
)
from takumi.roles import permissions


class DebugQuery:
    """A selection of debug queries for developers only"""

    influencer_debug = fields.Field(
        fields.GenericScalar, influencer_id=arguments.UUID(required=True)
    )

    @permissions.developer.require()
    def resolve_influencer_debug(self, info, influencer_id: str) -> Dict:
        influencer: Influencer = get_influencer_or_404(influencer_id)

        user: User = influencer.user
        facebook_account: Optional[FacebookAccount] = user.facebook_account
        instagram_account: Optional[InstagramAccount] = influencer.instagram_account
        tiktok_account: Optional[TikTokAccount] = influencer.tiktok_account
        device: Optional[Device] = user.device

        output = {}

        output["user"] = {
            "id": user.id,
            "email": user.email,
            "youtube_channel_url": user.youtube_channel_url,
            "tiktok_username": user.tiktok_username,
            "last_10_events": [
                (
                    event.type,
                    event.created.isoformat(),
                    event.event,
                )
                for event in user.events[-10:]
            ],
        }

        output["influencer"] = {
            "id": influencer.id,
            "state": influencer.state,
            "skip_self_tagging": influencer.skip_self_tagging,
            "audience_insight_expires": influencer.audience_insight_expires,
            "has_valid_audience_insights": influencer.has_valid_audience_insight,
            "social_accounts_chosen": influencer.social_accounts_chosen,
            "has_at_least_one_social_account": influencer.has_at_least_one_social_account,
        }

        if device is not None:
            output["device"] = {
                "id": device.id,
                "created": device.created.isoformat(),
                "active": device.active,
                "device_token": device.device_token,
            }
        else:
            output["device"] = None  # type: ignore

        if facebook_account is not None:
            output["facebook_account"] = {
                "id": facebook_account.id,
                "active": facebook_account.active,
                "facebook_pages": [page.id for page in facebook_account.facebook_pages],
                "permissions": facebook_account.permissions,
            }

        else:
            output["facebook_account"] = None  # type: ignore

        if instagram_account is not None:
            output["instagram_account"] = {
                "id": instagram_account.id,
                "active": instagram_account.active,
                "ig_username": instagram_account.ig_username,
            }
            facebook_page: Optional[FacebookPage] = instagram_account.facebook_page
            if facebook_page is not None:
                output["instagram_account"]["facebook_page"] = {
                    "id": facebook_page.id,
                    "active": facebook_page.active,
                    "facebook_account_id": facebook_page.facebook_account_id,
                }
            else:
                output["instagram_account"]["facebook_page"] = None  # type: ignore
        else:
            output["instagram_account"] = None  # type: ignore

        if tiktok_account is not None:
            output["tiktok_account"] = {
                "id": tiktok_account.id,
                "nickname": tiktok_account.nickname,
                "username": tiktok_account.username,
            }
        else:
            output["tiktok_account"] = None  # type:ignore

        return output
