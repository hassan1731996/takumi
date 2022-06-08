import datetime as dt
import re
from typing import Dict, List
from urllib.parse import urlparse

from flask import Response, jsonify

from takumi.models import Campaign, Gig, Insight, InsightEvent
from takumi.models.insight import STATES as INSIGHT_STATES
from takumi.models.post import PostTypes
from takumi.reporting import get_posts_gigs_stats_csv
from takumi.services import CampaignService, InstagramPostService, InstagramStoryService
from takumi.views.blueprint import api


def generate_post_stats(post):
    sentiment = post.average_sentiment()

    comment_stat_count = post.comment_stat_count()

    emoji_count = comment_stat_count["emojis"].most_common(5)
    hashtag_count = comment_stat_count["hashtags"].most_common(5)

    # Each value/count from collections.Counter.most_common is a tuple of (value, count)
    emojis = [{"value": x[0], "count": x[1]} for x in emoji_count]
    hashtags = [{"value": x[0], "count": x[1]} for x in hashtag_count]

    return {
        "caption_sentiment": {"value": sentiment["captions"]},
        "comment_sentiment": {"value": sentiment["comments"]},
        "hashtags": hashtags,
        "emojis": emojis,
    }


@api.route("/campaigns/report/<uuid:report_token>", methods=["GET"])
def post_report(report_token):
    campaign = Campaign.query.filter(Campaign.report_token == report_token).first()
    if campaign is None:
        return jsonify({"error": "Campaign not found"}), 404

    def iter_post_data():
        for post in campaign.posts:
            yield {"id": post.id, "stats": generate_post_stats(post)}

    return jsonify({"id": campaign.id, "posts": list(iter_post_data())})


@api.route("/campaigns/csv/report/<uuid:report_token>", methods=["GET"])
def post_gig_stats_get(report_token):
    campaign = Campaign.query.filter(Campaign.report_token == report_token).first()
    if campaign is None:
        return jsonify({"error": "Campaign not found"}), 404

    if len(campaign.posts) == 0:
        return jsonify({"error": "Campaign has no posts"}), 404

    with get_posts_gigs_stats_csv(campaign.posts) as data:
        return Response(
            data,
            mimetype="text/csv",
            headers={
                "content-disposition": "attachment; filename=gig_stats.csv",
                "content-type": "text/csv",
            },
        )


MediasPerPost = Dict[str, Dict[str, List[str]]]


def get_post_urls(campaign: Campaign) -> MediasPerPost:
    urls = lambda ic: [urlparse(media.url).path for media in ic.media]
    username = lambda ic: ic.gig.offer.influencer.username

    medias_per_post = {}
    for post_idx, post in enumerate(campaign.posts):
        if post.post_type == PostTypes.story:
            instagram_contents = InstagramStoryService.get_instagram_stories_from_post(post.id)
        else:
            instagram_contents = InstagramPostService.get_instagram_posts_from_post(post.id)

        post_key = "Post {}".format(post_idx + 1)
        medias_per_post[post_key] = {
            username(instagram_content): urls(instagram_content)
            for instagram_content in instagram_contents
        }

    return medias_per_post


def get_submission_urls(campaign: Campaign) -> MediasPerPost:
    """Collect all the submissions that have been at least approved by Takumi"""
    urls = lambda sub: [urlparse(media.url).path for media in sub.media]
    username = lambda gig: gig.offer.influencer.username

    medias_per_post: MediasPerPost = {}
    for post_idx, post in enumerate(campaign.posts):
        post_key = "Post {}".format(post_idx + 1)
        medias_per_post[post_key] = {}
        for gig in post.gigs:
            if gig.state in (Gig.STATES.REVIEWED, Gig.STATES.APPROVED):
                medias_per_post[post_key][username(gig)] = urls(gig.submission)

    return medias_per_post


def get_insights_for_week(campaign, year, week):
    """Return a list of insights for the given week in a year

    Returns only insights that were approved in the given week

    Week number follows ISO week date as defined in ISO 8601
    """
    urls = lambda insight: [urlparse(media.url).path for media in insight.media]
    username = lambda insight: insight.gig.offer.influencer.username

    start_date = dt.datetime.strptime(f"{year}-W{week}-1", "%G-W%V-%u").replace(
        tzinfo=dt.timezone.utc
    )
    end_date = start_date + dt.timedelta(days=7)

    insights_per_post = {}
    for post_idx, post in enumerate(campaign.posts):
        insights = (
            Insight.query.join(Gig)
            .join(InsightEvent)
            .filter(
                Gig.post_id == post.id,
                Insight.state == INSIGHT_STATES.APPROVED,
                InsightEvent.type == "approve",
                InsightEvent.created > start_date,
                InsightEvent.created < end_date,
            )
        )
        post_key = f"Post {post_idx + 1}"
        insights_per_post[post_key] = {username(insight): urls(insight) for insight in insights}
    return insights_per_post


@api.route("/campaigns/<uuid:report_token>/media_urls", methods=["GET"])
@api.route("/campaigns/<uuid:report_token>/post_urls", methods=["GET"])
def get_campaign_post_urls(report_token):
    campaign = CampaignService.get_by_report_token(report_token)
    if campaign is None:
        return jsonify({"error": "Campaign not found"}), 404

    medias_per_post = get_post_urls(campaign)

    ascii_name = campaign.name.encode("ascii", errors="ignore").decode("utf-8")
    path_safe = re.sub(r"[^\w\s-]", "", ascii_name).strip()

    return jsonify({path_safe: medias_per_post})


@api.route("/campaigns/<uuid:submissions_token>/submission_urls", methods=["GET"])
def get_campaign_submission_urls(submissions_token):
    campaign = Campaign.query.filter(Campaign.submissions_token == submissions_token).one_or_none()

    if campaign is None:
        return jsonify({"error": "Campaign not found"}), 404

    medias_per_post = get_submission_urls(campaign)

    ascii_name = campaign.name.encode("ascii", errors="ignore").decode("utf-8")
    path_safe = re.sub(r"[^\w\s-]", "", ascii_name).strip()

    return jsonify({path_safe: medias_per_post})
