from typing import Dict, List, Optional, TypedDict, cast

from flask_login import current_user
from graphene import ObjectType
from sentry_sdk import capture_exception

from core.facebook.instagram import InstagramAPI

from takumi.extensions import instascrape
from takumi.gql import arguments, fields
from takumi.gql.exceptions import QueryException
from takumi.ig.business_discovery import BusinessDiscoveryException, get_profile, get_profile_media
from takumi.ig.utils import calculate_hashtag_stats
from takumi.models import Influencer, InstagramAccount, InstagramPost
from takumi.models.media import Media
from takumi.roles import permissions


def _generate_connection_field(connection_node, **kwargs):
    class _PageInfo(ObjectType):
        has_next_page = fields.Boolean()
        has_previous_page = fields.Boolean()
        start_cursor = fields.String()
        end_cursor = fields.String()

    class _Edge(ObjectType):
        node = fields.Field(connection_node)

    class _Summary(ObjectType):
        hashtags = fields.List(fields.List(fields.String))

    class _Connection(ObjectType):
        edges = fields.List(_Edge)
        page_info = fields.Field(_PageInfo)
        summary = fields.Field(_Summary)
        count = fields.Int()

    return fields.Field(_Connection, **kwargs)


def _get_page_info(page):
    data = page.get("data")
    pagination = page.get("pagination")

    if len(data) == 0:
        return {
            "has_next_page": False,
            "has_previous_page": False,
            "start_cursor": None,
            "end_cursor": None,
        }

    has_next_page = pagination.get("next") is not None
    has_previous_page = pagination.get("prev") is not None

    start_cursor = None
    end_cursor = pagination["next"].split("/")[-1] if "next" in pagination else None

    return {
        "has_next_page": has_next_page,
        "has_previous_page": has_previous_page,
        "start_cursor": start_cursor,
        "end_cursor": end_cursor,
    }


def _assemble_instagram_post(media: Dict) -> InstagramPost:
    if media["media_type"] == "VIDEO":
        media["type"] = "video"
    else:
        media["type"] = "image"

    permalink = media.get("permalink")
    shortcode = permalink and permalink.split("/")[-2] or None

    instagram_post = InstagramPost(
        caption=media.get("caption", ""),
        shortcode=shortcode,
        ig_post_id=media.get("id", None),
        likes=media.get("like_count", 0),
        comments=media.get("comments_count", 0),
    )
    instagram_post.media = [  # type: ignore
        Media.from_dict(
            {
                "type": "video" if media["media_type"] == "VIDEO" else "image",
                "url": media.get("media_url"),
            },
            instagram_post,
        )
    ]
    return instagram_post


class InsightDict(TypedDict, total=False):
    engagement: int
    impressions: int
    reach: int
    saved: int


class MediaDict(TypedDict):
    comments_count: int
    like_count: int
    id: str
    ig_id: str
    media_url: str
    timestamp: str
    permalink: str
    insights: Optional[InsightDict]


class ProfileDict(TypedDict):
    biography: str
    id: str
    ig_id: int
    followers_count: int
    follows_count: int
    media_count: int
    name: str
    profile_picture_url: str
    username: str
    website: str
    media: Optional[List[MediaDict]]


class InstagramQuery:
    """These queries effectively proxy queries to instascrape

    They implement the relay connection interface, where applicable, in a
    custom way, since we don't have actual database access on instagram.
    """

    instagram_media_by_username = _generate_connection_field(
        "InstagramPost",
        username=arguments.String(),
        id=arguments.UUID(),
        after=arguments.String(),
    )
    instagram_user = fields.Field("InstagramUser", username=arguments.String())
    instagram_profile = fields.Field("InstagramAPIProfile", username=arguments.String())

    @permissions.public.require()
    def resolve_instagram_media_by_username(root, info, username=None, id=None, after=None):
        if username is None:
            if id is None:
                raise QueryException("Need to provide either id or username")
            influencer = Influencer.query.get(id)
            instagram_account = influencer.instagram_account
            if not instagram_account:
                raise QueryException("No instagram account for the influencer id")
            username = instagram_account.ig_username

        try:
            profile = get_profile(username)
            media = get_profile_media(username)
        except BusinessDiscoveryException:
            profile = None
            media = None

        if not media:
            edges = []
            summary = {}
            count = 0
        else:
            edges = [{"node": _assemble_instagram_post(node)} for node in media]
            summary = {"hashtags": calculate_hashtag_stats(media)}
            count = profile["media_count"]

        return {"edges": edges, "page_info": {}, "summary": summary, "count": count}

    @permissions.public.require()
    def resolve_instagram_user(root, info, username=None):
        if username is None:
            return None
        try:
            return instascrape.get_user(username)
        except Exception:
            return None

    @permissions.influencer.require()
    def resolve_instagram_profile(root, info, username: Optional[str] = None) -> ProfileDict:
        account: Optional[InstagramAccount]
        if username is not None and permissions.developer.can():
            account = InstagramAccount.by_username(username)
        else:
            account = current_user.influencer and current_user.influencer.instagram_account

        if account is None:
            raise QueryException("Instagram profile not found")

        if account.facebook_page is None or account.facebook_page.instagram_api is None:
            raise QueryException("Account not linked to Facebook")

        api: InstagramAPI = account.facebook_page.instagram_api

        profile: ProfileDict = cast(ProfileDict, api.get_profile())
        media: List[MediaDict] = api.get_medias(
            limit=6,
            fields=[
                "comments_count",
                "like_count",
                "id",
                "ig_id",
                "media_url",
                "timestamp",
                "permalink",
            ],
        )

        for item in media:
            try:
                insights: InsightDict = cast(InsightDict, api.get_media_insights(item["id"]))
            except Exception:  # XXX: Figure out possible errors?
                capture_exception()
                insights = {}
            item["insights"] = insights

        profile["media"] = media

        return profile
