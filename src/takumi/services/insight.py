import datetime as dt

from flask_login import current_user
from sqlalchemy import and_, func, or_

from takumi.constants import ALL_REGIONS, ALL_SUPPORTED_REGIONS
from takumi.events.insight import InsightLog
from takumi.extensions import db
from takumi.models import Campaign, Gig, Insight, InsightEvent, Post, Region, Targeting
from takumi.models.insight import STATES as INSIGHT_STATES
from takumi.models.insight import TYPES as INSIGHT_TYPES
from takumi.ocr import analyse_post_insight
from takumi.services import Service
from takumi.services.exceptions import MediaNotFoundException, OfferAlreadyClaimed
from takumi.utils import uuid4_str


class InsightService(Service):
    """
    Represents the business model for Insight. This isolates the database
    from the application.
    """

    SUBJECT = Insight
    LOG = InsightLog

    @property
    def insight(self):
        return self.subject

    # GET
    @staticmethod
    def get_by_id(id):
        return Insight.query.get(id)

    @staticmethod
    def get_by_gig_id(gig_id):
        return Insight.query.filter(Insight.gig_id == gig_id).one_or_none()

    @staticmethod
    def get_insights(args):
        query = Insight.query

        if "processed" in args:
            if args["processed"] is True:
                query = query.filter(Insight.state == INSIGHT_STATES.APPROVED)
            else:
                # treat requires_resubmit as not submitted
                query = query.filter(Insight.state == INSIGHT_STATES.SUBMITTED)

        query = query.join(Gig).join(Post).join(Campaign)

        if "campaign_id" in args:
            query = query.filter(Post.campaign_id == args["campaign_id"])
        elif "post_id" in args:
            query = query.filter(Post.id == args["post_id"])
        elif "mine" in args and args["mine"] is True:
            query = query.filter(
                or_(
                    Campaign.owner_id == current_user.id,
                    Campaign.campaign_manager_id == current_user.id,
                    Campaign.community_manager_id == current_user.id,
                )
            )

        if "region" in args and args["region"] not in (ALL_REGIONS, ALL_SUPPORTED_REGIONS):
            country = args["region"]
            query = query.join(Targeting).filter(
                Targeting.regions.any((Region.path[1] == country) | (Region.id == country))
            )
        return query

    @staticmethod
    def get_approved_insight_weeks(campaign):
        """Return a list of weeks + years that have approved insights"""
        sub = (
            db.session.query(
                InsightEvent.insight_id, func.max(InsightEvent.created).label("approved")
            )
            .filter(InsightEvent.type == "approve")
            .group_by(InsightEvent.insight_id)
        ).subquery()

        q = (
            db.session.query(InsightEvent, sub.c.approved)
            .join(
                sub,
                and_(
                    sub.c.insight_id == InsightEvent.insight_id,
                    sub.c.approved == InsightEvent.created,
                ),
            )
            .join(Insight)
            .join(Gig)
            .join(Post)
            .filter(
                Post.campaign_id == campaign.id,
                Insight.state == INSIGHT_STATES.APPROVED,
                InsightEvent.type == "approve",
            )
        )
        if not q.count():
            return

        first = q.order_by(InsightEvent.created).first().approved
        last = q.order_by(InsightEvent.created.desc()).first().approved

        first_year, first_week, _ = first.isocalendar()
        last_year, last_week, _ = last.isocalendar()

        current_year = first_year
        current_week = first_week

        while current_year < last_year or current_week <= last_week:
            week_date = dt.datetime.strptime(
                f"{current_year}-W{current_week}-1", "%G-W%V-%u"
            ).replace(tzinfo=dt.timezone.utc)

            count = q.filter(
                InsightEvent.created > week_date,
                InsightEvent.created < week_date + dt.timedelta(days=7),
            ).count()

            if count:
                yield current_year, current_week, count

            if current_week == 52:
                current_week = 1
                current_year += 1
            else:
                current_week += 1

    # POST
    @staticmethod
    def create(gig):

        insight = Insight(id=uuid4_str(), gig=gig, followers=gig.offer.influencer.followers)
        db.session.add(insight)
        db.session.commit()

        return insight

    # PUT
    def add_media(self, insight_urls):
        self.log.add_event("add_media", {"urls": insight_urls})

        if self.insight.type == INSIGHT_TYPES.POST_INSIGHT:
            # Run OCR after adding new media to post insights
            from takumi.tasks.ocr import analyse_post_insight

            analyse_post_insight.delay(self.insight.id)

    def remove_media(self, media_id):
        from takumi.services import MediaService

        media = MediaService.get_insight_media_by_id(media_id)
        if not media:
            raise MediaNotFoundException(f"Insight media ({media_id}) not found")

        self.log.add_event("remove_media", {"media_id": media.id, "url": media.url})
        db.session.delete(media)

    def update_story_insight(self, args):  # noqa: C901
        if "reach" in args:
            self.log.add_event("set_reach", {"reach": args["reach"]})
        if "non_followers_reach" in args:
            self.log.add_event(
                "set_non_followers_reach", {"non_followers_reach": args["non_followers_reach"]}
            )
        if "views" in args:
            self.log.add_event("set_views", {"views": args["views"]})
        if "shares" in args:
            self.log.add_event("set_shares", {"shares": args["shares"]})
        if "replies" in args:
            self.log.add_event("set_replies", {"replies": args["replies"]})
        if "link_clicks" in args:
            self.log.add_event("set_link_clicks", {"link_clicks": args["link_clicks"]})
        if "sticker_taps" in args:
            self.log.add_event("set_sticker_taps", {"sticker_taps": args["sticker_taps"]})
        if "profile_visits" in args:
            self.log.add_event("set_profile_visits", {"profile_visits": args["profile_visits"]})
        if "follows" in args:
            self.log.add_event("set_follows", {"follows": args["follows"]})
        if "back_navigations" in args:
            self.log.add_event(
                "set_back_navigations", {"back_navigations": args["back_navigations"]}
            )
        if "forward_navigations" in args:
            self.log.add_event(
                "set_forward_navigations", {"forward_navigations": args["forward_navigations"]}
            )
        if "next_story_navigations" in args:
            self.log.add_event(
                "set_next_story_navigations",
                {"next_story_navigations": args["next_story_navigations"]},
            )
        if "exited_navigations" in args:
            self.log.add_event(
                "set_exited_navigations", {"exited_navigations": args["exited_navigations"]}
            )
        if "impressions" in args:
            self.log.add_event("set_impressions", {"impressions": args["impressions"]})
        if "emails" in args:
            self.log.add_event("set_emails", {"emails": args["emails"]})
        if "website_clicks" in args:
            self.log.add_event("set_website_clicks", {"website_clicks": args["website_clicks"]})

    def update_post_insight(self, args):  # noqa: C901
        if "reach" in args:
            self.log.add_event("set_reach", {"reach": args["reach"]})
        if "non_followers_reach" in args:
            self.log.add_event(
                "set_non_followers_reach", {"non_followers_reach": args["non_followers_reach"]}
            )
        if "likes" in args:
            self.log.add_event("set_likes", {"likes": args["likes"]})
        if "comments" in args:
            self.log.add_event("set_comments", {"comments": args["comments"]})
        if "shares" in args:
            self.log.add_event("set_shares", {"shares": args["shares"]})
        if "bookmarks" in args:
            self.log.add_event("set_bookmarks", {"bookmarks": args["bookmarks"]})
        if "calls" in args:
            self.log.add_event("set_calls", {"calls": args["calls"]})
        if "emails" in args:
            self.log.add_event("set_emails", {"emails": args["emails"]})
        if "get_directions" in args:
            self.log.add_event("set_get_directions", {"get_directions": args["get_directions"]})
        if "profile_visits" in args:
            self.log.add_event("set_profile_visits", {"profile_visits": args["profile_visits"]})
        if "replies" in args:
            self.log.add_event("set_replies", {"replies": args["replies"]})
        if "website_clicks" in args:
            self.log.add_event("set_website_clicks", {"website_clicks": args["website_clicks"]})
        if "follows" in args:
            self.log.add_event("set_follows", {"follows": args["follows"]})

        impressions_updated = False
        if "from_hashtags_impressions" in args:
            impressions_updated = True
            self.log.add_event(
                "set_from_hashtags_impressions",
                {"from_hashtags_impressions": args["from_hashtags_impressions"]},
            )
        if "from_home_impressions" in args:
            impressions_updated = True
            self.log.add_event(
                "set_from_home_impressions",
                {"from_home_impressions": args["from_home_impressions"]},
            )
        if "from_explore_impressions" in args:
            impressions_updated = True
            self.log.add_event(
                "set_from_explore_impressions",
                {"from_explore_impressions": args["from_explore_impressions"]},
            )
        if "from_location_impressions" in args:
            impressions_updated = True
            self.log.add_event(
                "set_from_location_impressions",
                {"from_location_impressions": args["from_location_impressions"]},
            )
        if "from_profile_impressions" in args:
            impressions_updated = True
            self.log.add_event(
                "set_from_profile_impressions",
                {"from_profile_impressions": args["from_profile_impressions"]},
            )
        if "from_other_impressions" in args:
            impressions_updated = True
            self.log.add_event(
                "set_from_other_impressions",
                {"from_other_impressions": args["from_other_impressions"]},
            )

        if impressions_updated:
            from takumi.services import InfluencerService

            InfluencerService(self.insight.gig.offer.influencer).update_impressions_ratio()

    def approve(self):
        self.log.add_event("approve")

        gig = self.insight.gig

        if not gig.offer.is_claimable:
            if gig.is_passed_review_period and gig.offer.has_all_gigs_claimable():
                from takumi.services import OfferService

                OfferService(gig.offer).set_claimable()

    def request_resubmission(self, reason):
        if self.insight.gig.offer.claimed is not None:
            raise OfferAlreadyClaimed(
                "Unable to request insights resubmission for an offer that has been claimed"
            )

        if self.insight.gig.offer.is_claimable:
            from takumi.services import OfferService

            OfferService(self.insight.gig.offer).unset_claimable()

        self.log.add_event("request_resubmit", {"reason": reason})

    def run_ocr(self):
        values = analyse_post_insight(self.insight)

        values = {
            key: {"value": ocr_value.value, "confidence": ocr_value.confidence}
            for key, ocr_value in values.items()
        }

        self.log.add_event("set_ocr_values", {"values": values})
