import datetime as dt

from sentry_sdk import capture_exception

from takumi.error_codes import LINK_GIG_ERROR_CODE
from takumi.events.gig import GigLog
from takumi.events.instagram_post import InstagramPostLog
from takumi.extensions import db
from takumi.models import Gig, InstagramPost, Media
from takumi.models.media import TYPES as MEDIA_TYPES
from takumi.models.media import UnknownMediaTypeException
from takumi.services import Service
from takumi.services.exceptions import (
    CreateInstagramPostException,
    GigNotFoundException,
    InvalidMediaDictException,
    InvalidMediaException,
    MediaNotFoundException,
    UnknownMediaFormatException,
    UnlinkGigException,
    UpdateMediaThumbnailException,
    UpdateMediaUrlException,
)
from takumi.tasks import instagram_post as instagram_post_tasks
from takumi.utils import uuid4_str
from takumi.validation.errors import ValidationError
from takumi.validation.media import InstagramMediaValidator


class InstagramPostService(Service):
    """
    Represents the business model for InstagramPost. This isolates the database
    from the application.
    """

    SUBJECT = InstagramPost
    LOG = InstagramPostLog

    @property
    def instagram_post(self):
        return self.subject

    @staticmethod
    def _interpret_ig_media(ig_media, url_key="url"):
        ig_media["type"] = ig_media.get("type", ig_media.get("media_type", "")).lower()
        ig_media["url"] = ig_media.get("url", ig_media.get("media_url"))

        if ig_media.get("type") == "image":
            if not ig_media["url"]:
                raise InvalidMediaDictException("Keys missing from image dict")
            return {"type": "image", "url": ig_media[url_key]}
        elif ig_media.get("type") == "video":
            if not ig_media["url"] or (
                "thumbnail_url" not in ig_media and "video_url" not in ig_media
            ):
                raise InvalidMediaDictException("Keys missing from video dict")
            return {
                "type": "video",
                "url": ig_media.get("video_url", ig_media["url"]),
                "thumbnail": ig_media.get("thumbnail_url", ig_media["url"]),
            }

        raise UnknownMediaFormatException("Unknown Media Format")

    @staticmethod
    def _interpret_ig_story(ig_story):
        if ig_story["is_video"]:
            return {
                "type": "video",
                "url": ig_story["video_url"],
                "thumbnail": ig_story["display_url"],
            }
        else:
            return {"type": "image", "url": ig_story["display_url"]}

    @classmethod
    def _assemble_media(cls, ig_media, instagram_post):
        ig_media["type"] = ig_media.get("type", ig_media.get("media_type", "")).lower()

        if not ig_media["type"]:
            raise UnknownMediaFormatException("Unknown Media Format")

        if ig_media["type"] == "gallery":
            return [
                Media.from_dict({"order": idx, **cls._interpret_ig_media(m)}, instagram_post)
                for idx, m in enumerate(ig_media["gallery"])
            ]
        if ig_media["type"] == "carousel_album":  # Instagram API Album
            influencer = instagram_post.gig.offer.influencer
            children = influencer.instagram_api.get_media_children(ig_media["id"])
            return [
                Media.from_dict({"order": idx, **cls._interpret_ig_media(m)}, instagram_post)
                for idx, m in enumerate(children)
            ]
        return [Media.from_dict(cls._interpret_ig_media(ig_media), instagram_post)]

    @classmethod
    def _create(cls, gig: Gig, shortcode: str, force: bool = False):
        influencer = gig.offer.influencer
        try:
            validator = InstagramMediaValidator.from_gig(gig)
            scraped_from_instagram = validator.validate(shortcode, force=force)
        except ValidationError:
            raise CreateInstagramPostException(
                "Unable to create instagram post",
                errors=validator.errors,
                error_code=LINK_GIG_ERROR_CODE,
            )
        except Exception:
            capture_exception()
            media_id = influencer.instagram_api.get_media_id_from_ig_media_id(shortcode)
            scraped_from_instagram = influencer.instagram_api.get_media(media_id)

        if force:
            gig.autoreport = False

        # initialise instagram_post with id to allow tiger_tasks to query
        instagram_post = InstagramPost(id=uuid4_str(), gig=gig)
        try:
            media = cls._assemble_media(scraped_from_instagram, instagram_post)
        except UnknownMediaTypeException:
            raise CreateInstagramPostException("Media is invalid")
        instagram_post.media = media
        log = InstagramPostLog(instagram_post)
        owner = scraped_from_instagram.get("owner", {})
        timestamp = scraped_from_instagram.get("timestamp")
        if timestamp and isinstance(timestamp, str):
            scraped_from_instagram["timestamp"] = dt.datetime.strptime(
                scraped_from_instagram["timestamp"], "%Y-%m-%dT%H:%M:%S+0000"
            )
            scraped_from_instagram["timestamp"] = scraped_from_instagram["timestamp"].replace(
                tzinfo=dt.timezone.utc
            )

        log.add_event(
            "create",
            {
                "gig_id": gig.id,
                "media": [m.url for m in media],
                "post": {"instructions": gig.post.instructions, "conditions": gig.post.conditions},
                "caption": scraped_from_instagram.get("caption"),
                "shortcode": scraped_from_instagram.get(
                    "shortcode", scraped_from_instagram.get("code")
                ),
                "ig_post_id": scraped_from_instagram.get("ig_id", scraped_from_instagram.get("id")),
                "link": scraped_from_instagram.get(
                    "permalink", scraped_from_instagram.get("link", "")
                ),
                "deleted": False,
                "sponsors": scraped_from_instagram.get("sponsors", []),
                "likes": scraped_from_instagram.get(
                    "like_count", scraped_from_instagram.get("likes", {}).get("count", 0)
                ),
                "comments": scraped_from_instagram.get(
                    "comments_count", scraped_from_instagram.get("comments", {}).get("count", 0)
                ),
                "posted": scraped_from_instagram.get(
                    "created", scraped_from_instagram.get("timestamp")
                ),
                "followers": owner.get("followers", owner.get("followers_count", 0)),
                "video_views": scraped_from_instagram.get("video_view_count", None),
                "scraped": dt.datetime.now(dt.timezone.utc),
            },
        )

        return instagram_post

    # GET
    @staticmethod
    def get_by_id(id):
        return InstagramPost.query.get(id)

    @staticmethod
    def get_instagram_posts_from_post(post_id):
        return (
            InstagramPost.query.join(Gig)
            .filter(
                InstagramPost.media != None,  # noqa: E711 strip out instagram_posts with no media
                Gig.post_id == post_id,
            )
            .all()
        )

    # POST
    @classmethod
    def create(cls, gig_id: str, shortcode: str, force: bool = False) -> InstagramPost:
        import takumi.tasks.cdn as cdn_tasks
        from takumi.services import GigService, OfferService

        gig = GigService.get_by_id(gig_id)
        if gig is None:
            raise GigNotFoundException(f"Could not find gig with id {gig_id}")

        offer = gig.offer

        instagram_post = cls._create(gig, shortcode, force)
        instagram_post.instagram_account_id = gig.offer.influencer.instagram_account.id

        # need to add instance to current session to allow querying the object
        db.session.add(instagram_post)

        gig_log = GigLog(gig)
        gig_log.add_event("mark_as_verified")

        if gig.is_passed_claimable_time:
            if offer.has_all_gigs_claimable():
                OfferService(offer).set_claimable()

        db.session.commit()

        cdn_tasks.upload_instagram_post_media_to_cdn_and_update_instagram_post.delay(
            instagram_post.id
        )

        instagram_post_tasks.scrape_and_update_instagram_post_media.delay(instagram_post.id)

        return instagram_post

    # PUT
    def update_media_url(self, media_id, url):
        media = Media.query.get(media_id)
        if media is None:
            raise MediaNotFoundException(f'Media not found for id "{media_id}"')
        if media.instagram_post != self.instagram_post:
            raise UpdateMediaUrlException(
                "<InstagramPost: {}> does not contain <Media: {}>".format(
                    self.instagram_post.id, media_id
                )
            )

        self.log.add_event(
            "set_media_url", {"media_id": media_id, "url": url, "original_url": media.url}
        )

    def update_media_thumbnail(self, media_id, thumbnail):
        media = Media.query.get(media_id)
        if media is None:
            raise MediaNotFoundException(f'Media not found for id "{media_id}"')
        if media.instagram_post != self.instagram_post:
            raise UpdateMediaThumbnailException(
                "<InstagramPost: {}> does not contain <Media: {}>".format(
                    self.instagram_post.id, media_id
                )
            )
        if media.type != MEDIA_TYPES.VIDEO:
            raise InvalidMediaException("Only video media has a thumbnail")

        self.log.add_event(
            "set_media_thumbnail",
            {"media_id": media_id, "thumbnail": thumbnail, "original_thumbnail": media.thumbnail},
        )

    def update_comments(self, comments):
        self.log.add_event("set_comments", {"comments": comments})

    def update_likes(self, likes):
        self.log.add_event("set_likes", {"likes": likes})

    def update_caption(self, caption):
        # caption_did_change = self.instagram_post.caption != caption
        # should_update_sentiment = caption_did_change or self.instagram_post.sentiment is None

        self.log.add_event("set_caption", {"caption": caption})

        """
        XXX: Temporary disable indico, as it's seems to have deprecated their API
        if (
            should_update_sentiment
            and self.instagram_post.gig.post.campaign.market.sentiment_supported
        ):
            if caption is None:
                self.update_sentiment(None)
            else:
                instagram_post_tasks.update_caption_sentiment.delay(self.instagram_post.id, caption)
        """

    def update_sentiment(self, sentiment):
        self.log.add_event("set_sentiment", {"sentiment": sentiment})

    def update_media_deleted(self, is_deleted):
        self.log.add_event("set_is_deleted", {"deleted": is_deleted})

    def update_followers(self, followers):
        self.log.add_event("set_followers", {"followers": followers})

    def update_scraped(self, date):
        self.log.add_event("set_scraped", {"scraped": date})

    def update_video_views(self, video_views):
        self.log.add_event("set_video_views", {"video_views": video_views})

    def unlink_gig(self):
        from takumi.events.gig import GigLog

        gig = self.instagram_post.gig
        if not gig:
            raise UnlinkGigException(
                f"<InstagramPost: {self.instagram_post.id}> has already been unlinked"
            )

        gig_log = GigLog(gig)
        gig_log.add_event("unlink_instagram_post", {"instagram_post_id": self.instagram_post.id})

        self.log.add_event("unlink_gig", {"gig_id": gig.id})
