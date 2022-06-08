from sqlalchemy import and_, func

from takumi.extensions import db
from takumi.models import (
    Gig,
    Insight,
    InstagramPost,
    InstagramStory,
    Media,
    Post,
    PostInsight,
    StoryFrame,
    StoryInsight,
)
from takumi.models.insight import STATES as INSIGHT_STATES


class PostReport:
    post: Post

    def __init__(self, post: Post):
        self.post = post

    @property
    def assets(self):
        gig_subq = (
            db.session.query(Gig.id).filter(Gig.post_id == self.post.id, Gig.is_live)
        ).subquery()

        story_frames_q = (
            db.session.query(StoryFrame.id)
            .join(InstagramStory)
            .filter(InstagramStory.gig_id.in_(gig_subq))
        )

        posts_subq = (
            db.session.query(InstagramPost.id).filter(InstagramPost.gig_id.in_(gig_subq))
        ).subquery()

        posts_asset_count_q = db.session.query(func.count(Media.id)).filter(
            and_(Media.owner_id.in_(posts_subq), Media.owner_type == "instagram_post")
        )

        return posts_asset_count_q.scalar() + story_frames_q.count()

    @property
    def submissions(self):
        return (
            db.session.query(func.count(Gig.id)).filter(Gig.post_id == self.post.id, Gig.is_live)
        ).scalar() or 0

    @property
    def processed_submissions(self):
        return (
            db.session.query(func.count(Gig.id))
            .join(Insight)
            .filter(
                Gig.post_id == self.post.id, Gig.is_live, Insight.state == INSIGHT_STATES.APPROVED
            )
        ).scalar() or 0

    @property
    def followers(self):
        """Actual followers per gig"""

        gig_subq = (
            db.session.query(Gig.id).filter(Gig.post_id == self.post.id, Gig.is_live)
        ).subquery()

        stories = (
            db.session.query(func.sum(InstagramStory.followers)).filter(
                InstagramStory.gig_id.in_(gig_subq)
            )
        ).scalar() or 0

        posts = (
            db.session.query(func.sum(InstagramPost.followers)).filter(
                InstagramPost.gig_id.in_(gig_subq)
            )
        ).scalar() or 0

        return posts + stories

    @property
    def website_clicks(self):
        return (
            db.session.query(func.sum(Insight.website_clicks))
            .join(Gig)
            .filter(
                Gig.post_id == self.post.id, Gig.is_live, Insight.state == INSIGHT_STATES.APPROVED
            )
        ).scalar() or 0

    @property
    def profile_visits(self):
        return (
            db.session.query(func.sum(Insight.profile_visits))
            .join(Gig)
            .filter(
                Gig.post_id == self.post.id, Gig.is_live, Insight.state == INSIGHT_STATES.APPROVED
            )
        ).scalar() or 0

    @property
    def reach(self):
        return (
            db.session.query(func.sum(Insight.reach))
            .join(Gig)
            .filter(
                Gig.post_id == self.post.id, Gig.is_live, Insight.state == INSIGHT_STATES.APPROVED
            )
        ).scalar() or 0


class Engagements:
    post: Post

    @property
    def engagements(self):
        result = (
            db.session.query(
                func.coalesce(func.sum(PostInsight.likes), 0).label("likes"),
                func.coalesce(func.sum(PostInsight.comments), 0).label("comments"),
                func.coalesce(func.sum(PostInsight.bookmarks), 0).label("bookmarks"),
                func.coalesce(func.sum(PostInsight.replies), 0).label("replies"),
                func.coalesce(func.sum(PostInsight.shares), 0).label("shares"),
            )
            .join(Gig)
            .filter(
                Gig.post_id == self.post.id,
                Gig.is_live,
                PostInsight.state == INSIGHT_STATES.APPROVED,
            )
        ).first()

        return {
            "likes": result.likes,
            "comments": result.comments,
            "saves": result.bookmarks,
            "replies": result.replies,
            "shares": result.shares,
            "total": sum(result),
        }

    @property
    def engagement_rate(self):
        total_followers = (
            db.session.query(func.sum(PostInsight.followers))
            .join(Gig)
            .filter(Gig.post_id == self.post.id, Gig.is_live)
        ).scalar()

        if not total_followers:
            return 0

        total_engagements = (
            db.session.query(
                func.coalesce(func.sum(PostInsight.likes), 0)
                + func.coalesce(func.sum(PostInsight.comments), 0)
                + func.coalesce(func.sum(PostInsight.bookmarks), 0)
                + func.coalesce(func.sum(PostInsight.replies), 0)
                + func.coalesce(func.sum(PostInsight.shares), 0)
            )
            .join(Gig)
            .filter(
                Gig.post_id == self.post.id,
                Gig.is_live,
                PostInsight.state == INSIGHT_STATES.APPROVED,
            )
        ).scalar()

        return total_engagements / total_followers


class Impressions:
    post: Post

    @property
    def impressions(self):
        result = (
            db.session.query(
                func.coalesce(func.sum(PostInsight.from_hashtags_impressions), 0).label("hashtags"),
                func.coalesce(func.sum(PostInsight.from_home_impressions), 0).label("home"),
                func.coalesce(func.sum(PostInsight.from_location_impressions), 0).label("location"),
                func.coalesce(func.sum(PostInsight.from_profile_impressions), 0).label("profile"),
                func.coalesce(func.sum(PostInsight.from_explore_impressions), 0).label("explore"),
                func.coalesce(func.sum(PostInsight.from_other_impressions), 0).label("other"),
            )
            .join(Gig)
            .filter(
                Gig.post_id == self.post.id,
                Gig.is_live,
                PostInsight.state == INSIGHT_STATES.APPROVED,
            )
        ).first()

        return {
            "home": result.home,
            "profile": result.profile,
            "hashtags": result.hashtags,
            "location": result.location,
            "explore": result.explore,
            "other": result.other,
            "total": sum(result),
        }

    @property
    def frequency(self):
        total_reach = (
            db.session.query(func.sum(PostInsight.reach))
            .join(Gig)
            .filter(
                Gig.post_id == self.post.id,
                Gig.is_live,
                PostInsight.state == INSIGHT_STATES.APPROVED,
            )
        ).scalar()

        if not total_reach:
            return 0

        total_impressions = (
            db.session.query(
                func.coalesce(func.sum(PostInsight.from_home_impressions), 0)
                + func.coalesce(func.sum(PostInsight.from_profile_impressions), 0)
                + func.coalesce(func.sum(PostInsight.from_hashtags_impressions), 0)
                + func.coalesce(func.sum(PostInsight.from_other_impressions), 0)
                + func.coalesce(func.sum(PostInsight.shares), 0)
            )
            .join(Gig)
            .filter(
                Gig.post_id == self.post.id,
                Gig.is_live,
                PostInsight.state == INSIGHT_STATES.APPROVED,
            )
        ).scalar()

        return total_impressions / total_reach


class StandardPostReport(PostReport, Impressions, Engagements):
    @property
    def projected_cpe(self):
        if self.post.price:
            engagements = (
                db.session.query(
                    func.coalesce(func.sum(PostInsight.likes), 0)
                    + func.coalesce(func.sum(PostInsight.comments), 0)
                    + func.coalesce(func.sum(PostInsight.bookmarks), 0)
                    + func.coalesce(func.sum(PostInsight.replies), 0)
                    + func.coalesce(func.sum(PostInsight.shares), 0)
                )
                .join(Gig)
                .filter(
                    Gig.post_id == self.post.id,
                    Gig.is_live,
                    PostInsight.state == INSIGHT_STATES.APPROVED,
                )
            ).scalar()
            if not engagements:
                return 0
            return int(self.post.price / engagements)


class VideoPostReport(PostReport, Impressions, Engagements):
    @property
    def video_views(self):
        return (
            db.session.query(func.sum(InstagramPost.video_views))
            .join(Gig)
            .filter(Gig.post_id == self.post.id, Gig.is_live)
        ).scalar() or 0

    @property
    def video_view_rate(self):
        if not self.followers:
            return 0
        return self.video_views / self.followers

    @property
    def projected_cpv(self):
        if self.post.price:
            return int(self.post.price / self.video_views)


class StoryPostReport(PostReport):
    @property
    def projected_cpe(self):
        if self.post.price:
            interactions = (
                db.session.query(func.sum(StoryInsight.interactions))
                .join(Gig)
                .filter(
                    Gig.post_id == self.post.id,
                    Gig.is_live,
                    StoryInsight.state == INSIGHT_STATES.APPROVED,
                )
            ).scalar()

            if not interactions:
                return 0

            return int(self.post.price / interactions)

    @property
    def impressions(self):
        return (
            db.session.query(func.sum(StoryInsight.impressions))
            .join(Gig)
            .filter(
                Gig.post_id == self.post.id,
                Gig.is_live,
                StoryInsight.state == INSIGHT_STATES.APPROVED,
            )
        ).scalar() or 0

    @property
    def frequency(self):
        total_reach = (
            db.session.query(func.sum(StoryInsight.reach))
            .join(Gig)
            .filter(
                Gig.post_id == self.post.id,
                Gig.is_live,
                StoryInsight.state == INSIGHT_STATES.APPROVED,
            )
        ).scalar()

        if not total_reach:
            return 0

        return self.impressions / total_reach

    @property
    def actions(self):
        result = (
            db.session.query(
                func.coalesce(func.sum(StoryInsight.link_clicks), 0).label("link_clicks"),
                func.coalesce(func.sum(StoryInsight.shares), 0).label("shares"),
                func.coalesce(func.sum(StoryInsight.replies), 0).label("replies"),
                func.coalesce(func.sum(StoryInsight.profile_visits), 0).label("profile_visits"),
                func.coalesce(func.sum(StoryInsight.website_clicks), 0).label("website_clicks"),
                func.coalesce(func.sum(StoryInsight.sticker_taps), 0).label("sticker_taps"),
            )
            .join(Gig)
            .filter(
                Gig.post_id == self.post.id,
                Gig.is_live,
                StoryInsight.state == INSIGHT_STATES.APPROVED,
            )
        ).first()

        return {
            "link_clicks": result.link_clicks,
            "shares": result.shares,
            "replies": result.replies,
            "profile_visits": result.profile_visits,
            "website_clicks": result.website_clicks,
            "sticker_taps": result.sticker_taps,
            "total": sum(result),
        }
