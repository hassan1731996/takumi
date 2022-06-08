import datetime as dt
from collections import Counter, namedtuple
from typing import TYPE_CHECKING, Tuple

from sqlalchemy import and_, case, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, SoftEnum, UUIDString, deprecated_column

from takumi.extensions import db
from takumi.schedule.post import MissingPostDeadlineException, PostSchedule
from takumi.utils import uuid4_str

from .gig import STATES as GIG_STATES
from .gig import Gig
from .instagram_post import InstagramPost
from .instagram_post_comment import InstagramPostComment

if TYPE_CHECKING:
    from takumi.models import Campaign  # noqa
Reminder = namedtuple("Reminder", ["label", "date", "message", "condition"])


class PostTypes:
    standard = "standard"
    video = "video"
    story = "story"
    reel = "reel"
    tiktok = "tiktok"
    youtube = "youtube"

    @staticmethod
    def get_types():
        return [
            PostTypes.standard,
            PostTypes.video,
            PostTypes.story,
            PostTypes.reel,
            PostTypes.tiktok,
            PostTypes.youtube,
        ]


class Post(db.Model):
    """A database entry representing a Takumi post.

    A post can be loosely defined as a brief, starting date, and a
    set of gigs posted to it.  Each gig, if not rejected or deleted (cancelled) receives a portion of
    the post "budget", and when that budget runs out, no more gigs can be posted.

    There are two types of posts in the Takumi system, those run on a budget + commission,
    which we refer to as "reach" posts, and those which run on a predefined number of posts/gigs,
    referred to as "assets" posts (see `type` field).  The main difference between the two are
    the reward per post calculation and the end conditions.

    "reach" posts end when the actual budget runs out, while "assets" posts end when the
    pre-defined number of gigs have been reserved/posted
    """

    __tablename__ = "post"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    opened = db.Column(UtcDateTime)
    submission_deadline = db.Column(UtcDateTime)
    deadline = db.Column(UtcDateTime)
    price = db.Column(db.Integer)

    events = db.Column(MutableList.as_mutable(JSONB), nullable=False, server_default="[]")
    conditions = db.Column(MutableList.as_mutable(JSONB), nullable=False, server_default="[]")
    start_first_hashtag = db.Column(db.Boolean, server_default="f")

    archived = db.Column(db.Boolean, server_default="f")
    requires_review_before_posting = db.Column(db.Boolean, server_default="t", nullable=False)
    scheduled_jobs = deprecated_column(
        "scheduled_jobs", MutableDict.as_mutable(JSONB), nullable=False, server_default="{}"
    )
    instructions = db.Column(db.String)
    brief = db.Column(MutableList.as_mutable(JSONB), nullable=False, server_default="[]")
    gallery_photo_count = db.Column(db.Integer, server_default=text("0"), nullable=False)
    post_type = db.Column(SoftEnum(*PostTypes.get_types()), server_default="standard")

    campaign_id = db.Column(
        UUIDString, db.ForeignKey("campaign.id", ondelete="cascade"), nullable=False, index=True
    )
    campaign = relationship("Campaign")

    allow_extra_media = db.Column(db.Boolean, server_default="t")

    def __repr__(self):
        return f"<Post: {self.id}>"

    @classmethod
    def from_url(cls, url):
        """Get post based on an admin url"""
        import re

        pattern = r".*/brands/\w+/[0-9a-fA-F\-]{36}/posts/(?P<post_id>[0-9a-fA-F\-]{36}).*"

        if match := re.match(pattern, url):
            return cls.query.get(match.group("post_id"))
        return None

    @property
    def supports_stats(self):
        return self.post_type != PostTypes.story

    @hybrid_property
    def reach(self):
        if self.post_type in [PostTypes.story, PostTypes.tiktok, PostTypes.youtube]:
            return 0
        return sum(
            [
                gig.instagram_post.followers
                for gig in self.gigs
                if gig.instagram_post and gig.is_live
            ]
        )

    @reach.expression  # type: ignore
    def reach(cls):
        return case(
            [(cls.post_type.in_([PostTypes.story, PostTypes.tiktok, PostTypes.youtube]), 0)],
            else_=select([func.sum(Gig.reach)])
            .where(and_(Gig.post_id == cls.id, Gig.is_live == True))
            .label("reach"),
        )

    @property
    def reach_static(self):
        return sum(gig.reach_static for gig in self.gigs)

    @property
    def reach_story(self):
        return sum(gig.reach_story for gig in self.gigs)

    @hybrid_property
    def impressions_static(self):
        """int: The sum of in-feed impressions from all the gigs of a particular post."""
        return sum(gig.impressions_static for gig in self.gigs)

    @impressions_static.expression  # type: ignore
    def impressions_static(cls):
        from takumi.models.gig import Gig  # noqa

        return (
            select([func.sum(Gig.impressions_static)])
            .where(Gig.post_id == cls.id)
            .label("impressions_static")
        )

    @hybrid_property
    def impressions_story(self):
        """int: The sum of story impressions from all the gigs of a particular post."""
        return sum(gig.impressions_story for gig in self.gigs)

    @impressions_story.expression  # type: ignore
    def impressions_story(cls):
        from takumi.models.gig import Gig  # noqa

        return (
            select([func.sum(Gig.impressions_story)])
            .where(Gig.post_id == cls.id)
            .label("impressions_story")
        )

    @property
    def impressions(self):
        return sum(gig.insight.impressions or 0 for gig in self.gigs if gig.insight)

    @hybrid_property
    def engagements(self):
        return self.likes + self.comments

    @engagements.expression  # type: ignore
    def engagements(cls):
        return case(
            [(cls.post_type.in_([PostTypes.story, PostTypes.tiktok, PostTypes.youtube]), 0)],
            else_=select([func.sum(Gig.engagements)])
            .where(and_(Gig.post_id == cls.id, Gig.is_live == True))
            .label("engagements"),
        )

    @property
    def engagement(self):
        if not self.reach:
            return 0
        return self.engagements / self.reach

    @property
    def expected_reach(self):
        return self.follower_counts["funded"]

    @property
    def likes(self):
        if self.post_type in [PostTypes.story, PostTypes.tiktok, PostTypes.youtube]:
            return 0
        return sum(
            [gig.instagram_post.likes for gig in self.gigs if gig.instagram_post and gig.is_live]
        )

    @property
    def comments(self):
        if self.post_type in [PostTypes.story, PostTypes.tiktok, PostTypes.youtube]:
            return 0
        return sum(
            [gig.instagram_post.comments for gig in self.gigs if gig.instagram_post and gig.is_live]
        )

    @property
    def video_views(self):
        if self.post_type in [PostTypes.story, PostTypes.tiktok, PostTypes.youtube]:
            return 0
        return sum([gig.instagram_post.video_views or 0 for gig in self.gigs if gig.is_live])

    @property
    def video_engagement(self):
        if not self.reach:
            return 0
        return self.video_views / self.reach

    @property
    def is_open(self):
        if self.opened:
            return self.opened <= dt.datetime.now(dt.timezone.utc) or False
        else:
            return True

    @property
    def mention(self):
        for c in self.conditions:
            if c["type"] == "mention":
                return c["value"]

    def get_event(self, type):
        for event in self.events:
            if event["_type"] == type:
                return event

    def recent_gig_posted(self):
        """Check if there are any fresh gigs on the post

        A fresh gig is one posted within the last 7 days in the post.
        """
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)

        count = (
            Gig.query.join(InstagramPost).filter(
                Gig.post_id == self.id, InstagramPost.posted > cutoff
            )
        ).count()

        return count > 0

    def average_sentiment(self):
        avg_comment_sentiment = (
            db.session.query(func.avg(InstagramPostComment.sentiment))
            .join(InstagramPost, InstagramPost.id == InstagramPostComment.instagram_post_id)
            .join(Gig, Gig.id == InstagramPost.gig_id)
            .filter(Gig.post_id == self.id)
            .filter(Gig.state != GIG_STATES.REJECTED)
        ).scalar()

        avg_caption_sentiment = (
            db.session.query(func.avg(InstagramPost.sentiment))
            .join(Gig)
            .filter(Gig.post_id == self.id)
            .filter(Gig.state != GIG_STATES.REJECTED)
        ).scalar()

        return {"captions": avg_caption_sentiment, "comments": avg_comment_sentiment}

    def comment_stat_count(self):
        from takumi.services import PostService

        result = PostService.get_comment_stats(self.id)

        if len(result) == 0:
            return {"emojis": Counter(), "hashtags": Counter()}

        # Need to do some magic to flatten out the results into flat list
        emoji_list, hashtag_list = zip(*result)

        flat_emoji_list = [item for sublist in emoji_list for item in sublist]
        flat_hashtag_list = [item for sublist in hashtag_list for item in sublist]

        emoji_count = Counter(flat_emoji_list)
        hashtag_count = Counter(flat_hashtag_list)

        return {"emojis": emoji_count, "hashtags": hashtag_count}

    @property
    def deadline_passed(self):
        if self.deadline is None:
            return False
        return self.deadline < dt.datetime.now(dt.timezone.utc)

    @property
    def seconds_until_expire(self):
        until_expiration = dt.datetime.now(dt.timezone.utc) - self.deadline
        if until_expiration.total_seconds() <= 0:
            return 0
        return int(round(until_expiration.total_seconds()))

    def is_overdue(self):
        return dt.datetime.now(dt.timezone.utc) > self.deadline

    @property
    def gig_events(self):
        gig_events = []

        for gig in self.gigs:
            for event in gig.events:
                if "update" not in event["_type"]:
                    gig_events.append(event)
        return gig_events

    @property
    def media_requirements(self):
        """The required media to be submitted for this post"""
        post_count = self.gallery_photo_count + 1

        if self.post_type == "video":
            return [{"type": "video"}] * post_count

        return [{"type": "any"}] * post_count

    @property
    def get_reminder_schedule(self) -> Tuple[Reminder, ...]:
        """Calculate the current reminder schedule for a post.
        Reminders are sent to influencers via push notification
        """
        try:
            schedule = PostSchedule(self)
        except MissingPostDeadlineException:
            # if no schedule could be created,
            # then no reminders should be created
            return tuple()

        submission_deadline = schedule.submission_deadline
        post_deadline = schedule.post_deadline
        name = self.campaign.name
        submission_reminders = (
            Reminder(
                label="SUBMISSION_REMINDER_48",
                date=submission_deadline - dt.timedelta(hours=48),
                message=f"Your submission for {name} is due in 48 hours",
                condition=lambda post_step: post_step == "SUBMIT_FOR_APPROVAL",
            ),
            Reminder(
                label="SUBMISSION_REMINDER_24",
                date=submission_deadline - dt.timedelta(hours=24),
                message=f"Your submission for {name} is due in 24 hours",
                condition=lambda post_step: post_step == "SUBMIT_FOR_APPROVAL",
            ),
            Reminder(
                label="SUBMISSION_REMINDER_6",
                date=submission_deadline - dt.timedelta(hours=6),
                message=f"Your submission for {name} is due soon",
                condition=lambda post_step: post_step == "SUBMIT_FOR_APPROVAL",
            ),
            Reminder(
                label="SUBMISSION_REMINDER_1",
                date=submission_deadline - dt.timedelta(hours=1),
                message=f"Please submit your content for {name} ASAP",
                condition=lambda post_step: post_step == "SUBMIT_FOR_APPROVAL",
            ),
        )
        post_reminders = (
            Reminder(
                label="POST_OPENS_REMINDER",
                date=self.opened,
                message=f"You can now post to the {name} campaign",
                condition=lambda post_step: post_step == "POST_TO_INSTAGRAM",
            ),
            Reminder(
                label="POST_TO_INSTAGRAM_REMINDER_24",
                date=post_deadline - dt.timedelta(hours=24),
                message=f"Posting deadline is tomorrow for the {name} campaign",
                condition=lambda post_step: post_step == "POST_TO_INSTAGRAM",
            ),
            Reminder(
                label="POST_TO_INSTAGRAM_REMINDER_6",
                date=post_deadline - dt.timedelta(hours=6),
                message=f"Posting deadline is approaching for the {name} campaign",
                condition=lambda post_step: post_step == "POST_TO_INSTAGRAM",
            ),
            Reminder(
                label="POST_TO_INSTAGRAM_REMINDER_1",
                date=post_deadline - dt.timedelta(hours=1),
                message=f"Please post ASAP to the {name} campaign",
                condition=lambda post_step: post_step == "POST_TO_INSTAGRAM",
            ),
            Reminder(
                label="POST_TO_INSTAGRAM_DEADLINE",
                date=post_deadline,
                message=f"Posting deadline is about to pass for the {name} campaign",
                condition=lambda post_step: post_step == "POST_TO_INSTAGRAM",
            ),
        )
        return submission_reminders + post_reminders
