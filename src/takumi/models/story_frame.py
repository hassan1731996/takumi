from typing import TYPE_CHECKING

from sqlalchemy import DDL, event, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import aliased, backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import MutableList, UUIDString
from core.facebook.instagram import InstagramMediaPostedBeforeBusinessAccountConversion

from takumi.extensions import db
from takumi.facebook_account import unlink_on_permission_error
from takumi.utils import uuid4_str

from .helpers import hybrid_property_subquery

if TYPE_CHECKING:
    from takumi.models import Influencer, InstagramStory, Media  # noqa


class StoryFrame(db.Model):
    __tablename__ = "story_frame"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())
    ig_story_id = db.Column(
        db.String, nullable=False, index=True
    )  # TODO: Set as unique once story frames belong to influencers only

    influencer_id = db.Column(
        UUIDString, db.ForeignKey("influencer.id"), nullable=False, index=True
    )

    influencer = relationship("Influencer")

    posted = db.Column(UtcDateTime, index=True)

    deleted = db.Column(UtcDateTime)

    instagram_story_id = db.Column(
        UUIDString,
        db.ForeignKey(
            "instagram_story.id", name="story_frame_instagram_story_id_fkey", ondelete="restrict"
        ),
        index=True,
    )
    instagram_story = relationship(
        "InstagramStory", backref=backref("story_frames", order_by="StoryFrame.posted")
    )

    media = relationship(
        "Media",
        primaryjoin="and_(StoryFrame.id == foreign(Media.owner_id), Media.owner_type == 'story_frame')",
        uselist=False,
        backref="story_frame",
    )
    mentions = db.Column(MutableList.as_mutable(JSONB), server_default="[]")
    locations = db.Column(MutableList.as_mutable(JSONB), server_default="[]")
    hashtags = db.Column(MutableList.as_mutable(JSONB), server_default="[]")
    swipe_up_link = db.Column(db.String)

    insights_unavailable = db.Column(db.Boolean)

    @hybrid_property
    def replies_insight(self):
        """int: All replies from story frame insight."""
        return (
            self.instagram_story_frame_insights[0].replies
            if self.instagram_story_frame_insights
            and self.instagram_story_frame_insights[0].replies
            else 0
        )

    @replies_insight.expression  # type: ignore
    def replies_insight(cls):
        from takumi.models.instagram_story_frame_insight import InstagramStoryFrameInsight  # noqa

        return (
            select([InstagramStoryFrameInsight.replies])
            .where(InstagramStoryFrameInsight.story_frame_id == cls.id)
            .order_by(InstagramStoryFrameInsight.created.desc())
            .limit(1)
            .label("replies_insight")
        )

    @hybrid_property
    def impressions(self):
        """int: All impressions from story frame insight."""
        return (
            self.instagram_story_frame_insights[0].impressions
            if self.instagram_story_frame_insights
            and self.instagram_story_frame_insights[0].impressions
            else 0
        )

    @impressions.expression  # type: ignore
    def impressions(cls):
        from takumi.models.instagram_story_frame_insight import InstagramStoryFrameInsight  # noqa

        return (
            select([InstagramStoryFrameInsight.impressions])
            .where(InstagramStoryFrameInsight.story_frame_id == cls.id)
            .order_by(InstagramStoryFrameInsight.created.desc())
            .limit(1)
            .label("impressions")
        )

    def update_instagram_insights(self):
        from takumi.models import InstagramStoryFrameInsight

        if self.insights_unavailable:
            return

        if not self.influencer.instagram_account:
            return

        facebook_page = self.influencer.instagram_account.facebook_page

        if not facebook_page or not facebook_page.active:
            return

        with unlink_on_permission_error(self.influencer.instagram_account.facebook_page):
            media_id = self.influencer.instagram_api.get_media_id_from_story_ig_media_id(
                self.ig_story_id
            )
            if media_id:
                try:
                    insight_data = self.influencer.instagram_api.get_media_insights(media_id)
                except InstagramMediaPostedBeforeBusinessAccountConversion:
                    self.insights_unavailable = True
                    db.session.commit()
                    return
                insight = InstagramStoryFrameInsight(story_frame_id=self.id)

                insight.exits = insight_data.get("exits")
                insight.impressions = insight_data.get("impressions")
                insight.reach = insight_data.get("reach")
                insight.replies = insight_data.get("replies")
                insight.taps_forward = insight_data.get("taps_forward")
                insight.taps_back = insight_data.get("taps_back")

                db.session.add(insight)
                db.session.commit()

    @hybrid_property_subquery
    def instagram_story_frame_insight_id(cls):
        from takumi.models import InstagramStoryFrameInsight

        AliasedStoryFrame = aliased(cls)

        return (
            db.session.query(InstagramStoryFrameInsight.id)
            .join(AliasedStoryFrame)
            .filter(AliasedStoryFrame.id == cls.id)
            .order_by(InstagramStoryFrameInsight.created.desc())
            .limit(1)
        )

    @property
    def instagram_story_frame_insight(self):
        from takumi.models import InstagramStoryFrameInsight

        if not self.instagram_story_frame_insight_id:
            return None

        return InstagramStoryFrameInsight.query.get(self.instagram_story_frame_insight_id)

    def __repr__(self):
        return f"<StoryFrame: {self.id} ({self.instagram_story})>"


# fmt: off
story_frame_triggers = DDL("""
CREATE TRIGGER cascade_story_frame_delete_media
AFTER DELETE ON story_frame
FOR EACH ROW EXECUTE PROCEDURE delete_related_media('story_frame');

CREATE TRIGGER cascade_story_frame_update_media
AFTER UPDATE ON story_frame
FOR EACH ROW EXECUTE PROCEDURE update_related_media('story_frame');
""")
# fmt: on
event.listen(
    StoryFrame.__table__, "after_create", story_frame_triggers.execute_if(dialect="postgresql")  # type: ignore
)
