import datetime as dt
from typing import List

import dateutil.parser
from sentry_sdk import capture_exception

from core.common.crypto import get_human_random_string
from core.facebook.instagram import InstagramError

from takumi.events.gig import GigLog
from takumi.events.instagram_story import InstagramStoryLog
from takumi.extensions import db, instascrape
from takumi.facebook_account import unlink_on_permission_error
from takumi.ig.instascrape import InstascrapeUnavailable, NotFound
from takumi.models import Config, Gig, InstagramStory, StoryFrame
from takumi.models.influencer import FacebookPageDeactivated, MissingFacebookPage
from takumi.models.media import TYPES as MEDIA_TYPES
from takumi.models.media import Image, Video
from takumi.models.post import PostTypes
from takumi.services import Service
from takumi.services.exceptions import (
    GigNotFoundException,
    InfluencerNotFound,
    InvalidMediaException,
    NotAStoryPostException,
    StoryFrameAlreadyPartOfAnotherInstagramStoryException,
    StoryFrameNotFoundException,
    StoryFrameNotMarkedAsPartOfCampaignException,
    UnlinkGigException,
)
from takumi.utils import uuid4_str


class InstagramStoryService(Service):
    """
    Represents the business model for InstagramStory. This isolates the database
    from the application.
    """

    SUBJECT = InstagramStory
    LOG = InstagramStoryLog

    @property
    def instagram_story(self):
        return self.subject

    @staticmethod
    def _create_story_frames_from_download(story, influencer, update_insights=True):
        if "data" in story:
            items = story["data"]["items"]
        else:
            items = story["items"]

        import takumi.tasks.cdn as cdn_tasks

        story_frames = []
        story_frame_ids = [s.get("ig_id", s["id"]) for s in items]
        existing_frames = StoryFrame.query.filter(StoryFrame.ig_story_id.in_(story_frame_ids)).all()
        for s in items:
            ig_id = s.get("ig_id", s["id"])
            story_frame = next((f for f in existing_frames if f.ig_story_id == ig_id), None)

            if not story_frame:
                mentions = []
                locations = []
                hashtags = []
                for tappable in s["tappable_objects"]:
                    if tappable["type"] == "mention":
                        mentions.append(
                            {"name": tappable["name"], "username": tappable["username"]}
                        )
                    elif tappable["type"] == "location":
                        locations.append({"id": tappable["id"], "name": tappable["short_name"]})
                    elif tappable["type"] == "hashtag":
                        hashtags.append({"id": tappable["id"], "name": tappable["name"]})

                story_frame = StoryFrame(
                    id=uuid4_str(),
                    ig_story_id=ig_id,
                    swipe_up_link=s.get("swipe_up_url"),
                    influencer_id=influencer.id,
                    locations=locations,
                    mentions=mentions,
                    hashtags=hashtags,
                    posted=dateutil.parser.parse(
                        s.get("timestamp", s.get("taken_at_timestamp"))
                    ).replace(tzinfo=dt.timezone.utc),
                )

                if s.get("is_video") or s.get("media_type") == "VIDEO":
                    url = s.get("media_url", s.get("video_url"))
                    thumbnail = s.get("thumbnail_url", s.get("display_url"))

                    if url is None or url is not None and "\x00" in url:
                        # We only get the thumbnail, set the url as thumbnail
                        url = thumbnail

                    media = Video(
                        url=url,
                        thumbnail=thumbnail,
                        owner_id=story_frame.id,
                        owner_type="story_frame",
                    )
                else:
                    media = Image(
                        url=s.get("media_url", s.get("display_url")),
                        owner_id=story_frame.id,
                        owner_type="story_frame",
                    )

                story_frame.media = media
                db.session.add(story_frame)
                db.session.commit()
                cdn_tasks.upload_story_media_to_cdn_and_update_story.delay(story_frame.id)

            story_frames.append(story_frame)

            if (
                update_insights
                and influencer.instagram_account.facebook_page
                and influencer.instagram_account.facebook_page.active
            ):
                with unlink_on_permission_error(influencer.instagram_account.facebook_page):
                    try:
                        story_frame.update_instagram_insights()
                    except FacebookPageDeactivated:
                        pass
                    except InstagramError:
                        capture_exception()

        return story_frames

    @staticmethod
    def download_story_frames(  # noqa: C901
        influencer_id: str, update_insights: bool = True
    ) -> List[StoryFrame]:
        from takumi.services import InfluencerService

        influencer = InfluencerService.get_by_id(influencer_id)

        if influencer is None:
            raise InfluencerNotFound("Cannot download story for non existing influencer")

        api_story_items = None
        cached = False
        if influencer.instagram_account.facebook_page is not None:
            try:
                with unlink_on_permission_error(influencer.instagram_account.facebook_page):
                    cached, api_story_items = influencer.instagram_api.get_stories(
                        cache_ttl=10, include_cache_status=True
                    )  # 10 sec TTL just in case the function accidentally gets called to often
            except (
                MissingFacebookPage,
                InstagramError,
                FacebookPageDeactivated,
            ) as e:
                if isinstance(e, InstagramError):
                    capture_exception()

        if Config.get("SCRAPE_STORIES").value is True:
            try:
                story = instascrape.get_user_story(influencer.username, nocache=not cached)

                if api_story_items:
                    for story_item in api_story_items:
                        try:
                            scraped_story_item = next(
                                s for s in story["data"]["items"] if s["id"] == story_item["ig_id"]
                            )
                        except StopIteration:
                            capture_exception()
                            return []
                        if story_item.get("media_url") is None:
                            story_item["media_url"] = scraped_story_item.get(
                                "video_url"
                            ) or scraped_story_item.get("display_url")
                        story_item["tappable_objects"] = scraped_story_item["tappable_objects"]
                        story_item["swipe_up_url"] = scraped_story_item.get("swipe_up_url")
                    story["data"]["items"] = api_story_items

            except (NotFound, InstascrapeUnavailable):
                return []
        else:
            if not api_story_items:
                return []

        story = {
            "items": [{**item, "tappable_objects": []} for item in api_story_items],
            "id": influencer.instagram_account.ig_user_id,
        }

        story_frames = InstagramStoryService._create_story_frames_from_download(
            story, influencer, update_insights=update_insights
        )

        if not cached:
            story_frames_last_24h = StoryFrame.query.filter(
                StoryFrame.influencer_id == influencer_id,
                StoryFrame.posted
                >= dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=23, minutes=50),
            )

            story_frame_ig_ids = [f.ig_story_id for f in story_frames]
            for story_frame in story_frames_last_24h:
                if story_frame.ig_story_id not in story_frame_ig_ids:
                    story_frame.deleted = dt.datetime.now(dt.timezone.utc)

            db.session.commit()

        return story_frames

    @staticmethod
    def _get_story_frame(story_frame_id):
        story_frame = StoryFrame.query.get(story_frame_id)
        if story_frame is None:
            raise StoryFrameNotFoundException(f'StoryFrame not found for id "{story_frame_id}"')

        return story_frame

    @staticmethod
    def update_media_url(story_frame_id, url):
        story_frame = InstagramStoryService._get_story_frame(story_frame_id)
        story_frame.media.url = url
        db.session.commit()

    @staticmethod
    def update_media_thumbnail(story_frame_id, thumbnail):
        story_frame = InstagramStoryService._get_story_frame(story_frame_id)
        if story_frame.media.type != MEDIA_TYPES.VIDEO:
            raise InvalidMediaException("Only video media has a thumbnail")
        story_frame.media.thumbnail = thumbnail
        db.session.commit()

    @staticmethod
    def _create_story(gig):
        instagram_story = InstagramStory(id=uuid4_str(), gig=gig)
        log = InstagramStoryLog(instagram_story)
        log.add_event(
            "create",
            {
                "gig_id": gig.id,
                "post": {"instructions": gig.post.instructions, "conditions": gig.post.conditions},
                "followers": gig.offer.influencer.followers,
            },
        )

        return instagram_story

    # GET
    @staticmethod
    def get_by_id(id):
        return InstagramStory.query.get(id)

    @staticmethod
    def get_story_frame_by_id(story_frame_id):
        return StoryFrame.query.get(story_frame_id)

    @staticmethod
    def get_instagram_stories_from_post(post_id):
        return InstagramStory.query.join(Gig).join(StoryFrame).filter(Gig.post_id == post_id).all()

    # POST
    @classmethod
    def create(cls, gig_id: str):
        from takumi.services import GigService, OfferService
        from takumi.tasks.scheduled.story_downloader import download_influencer_story_frames

        gig = GigService.get_by_id(gig_id)
        if gig is None:
            raise GigNotFoundException(f"Could not find gig with id {gig_id}")

        offer = gig.offer

        instagram_story = cls._create_story(gig)
        instagram_story.instagram_account = gig.offer.influencer.instagram_account

        # need to add instance to current session to allow querying the object
        db.session.add(instagram_story)

        if gig.is_passed_claimable_time:
            if offer.has_all_gigs_claimable():
                OfferService(offer).set_claimable()

        db.session.commit()

        download_influencer_story_frames.delay(gig.offer.influencer.id)
        return instagram_story

    @classmethod
    def copy_submission_to_story(cls, gig_id):
        from takumi.services import GigService

        gig = GigService.get_by_id(gig_id)
        if not gig:
            raise GigNotFoundException(f"Could not find gig with id {gig_id}")

        if gig.post.post_type != PostTypes.story:
            raise NotAStoryPostException(
                f"Can't create a story for a post type: {gig.post.post_type}"
            )

        instagram_story_id = gig.instagram_story.id if gig.instagram_story else None
        story_frames = []
        for media in gig.submission.media:
            story_frame = StoryFrame(
                id=uuid4_str(),
                ig_story_id=f"manuallyportedfromsubmission{get_human_random_string()}",
                influencer_id=gig.offer.influencer_id,
                posted=gig.instagram_story.created
                if gig.instagram_story
                else gig.submission.created,
            )

            if media.type == "video":
                story_media = Video(
                    url=media.url,
                    thumbnail=media.thumbnail,
                    owner_id=story_frame.id,
                    owner_type="story_frame",
                )
            else:
                story_media = Image(
                    url=media.url, owner_id=story_frame.id, owner_type="story_frame"
                )

            story_frame.media = story_media
            if instagram_story_id:
                story_frame.instagram_story_id = instagram_story_id

            story_frames.append(story_frame)
            db.session.add(story_frame)

        if not instagram_story_id:
            instagram_story = InstagramStory(id=uuid4_str(), gig=gig, story_frames=story_frames)
            log = InstagramStoryLog(instagram_story)
            log.add_event(
                "create",
                {
                    "info": "manually created instagram story from a submission",
                    "gig_id": gig.id,
                    "media": [s.media.url for s in instagram_story.story_frames],
                    "post": {
                        "instructions": gig.post.instructions,
                        "conditions": gig.post.conditions,
                    },
                    "followers": gig.offer.influencer.followers,
                },
            )

            db.session.add(instagram_story)
        db.session.commit()

        return gig.instagram_story

    def mark_as_posted(self):
        self.log.add_event("mark_as_posted")

    def unlink_gig(self):
        from takumi.events.gig import GigLog

        gig = self.instagram_story.gig
        if not gig:
            raise UnlinkGigException(
                f"<InstagramStory: {self.instagram_story.id}> has already been unlinked"
            )

        gig_log = GigLog(gig)
        gig_log.add_event("unlink_instagram_story", {"instagram_story_id": self.instagram_story.id})

        self.log.add_event("unlink_gig", {"gig_id": gig.id})

    def link_story_frame(self, story_frame_id, verify=True):
        story_frame = StoryFrame.query.get(story_frame_id)

        if story_frame is None:
            raise StoryFrameNotFoundException(f'StoryFrame not found for id "{story_frame_id}"')

        if story_frame.instagram_story_id != self.instagram_story.id:
            if story_frame.instagram_story is not None:
                raise StoryFrameAlreadyPartOfAnotherInstagramStoryException(
                    "StoryFrame {} is already part of a gig {}".format(
                        story_frame_id, story_frame.instagram_story.gig_id
                    )
                )

            story_frame.instagram_story_id = self.instagram_story.id
            self.log.add_event("link_frame", {"story_frame_id": story_frame_id})

        gig_log = GigLog(self.instagram_story.gig)
        if not self.instagram_story.gig.is_posted:
            gig_log.add_event("mark_as_posted")
        if verify and not self.instagram_story.gig.is_verified:
            gig_log.add_event("mark_as_verified")

    def unlink_story_frame(self, story_frame_id):
        story_frame = StoryFrame.query.get(story_frame_id)
        if story_frame is None:
            raise StoryFrameNotFoundException(f'StoryFrame not found for id "{story_frame_id}"')

        if story_frame.instagram_story != self.instagram_story:
            raise StoryFrameNotMarkedAsPartOfCampaignException(
                f"<StoryFrame: {story_frame_id}> is not marked as part of campaign"
            )

        self.log.add_event("unlink_frame", {"story_frame_id": story_frame_id})
