import datetime as dt
import os
from typing import List

from flask import request
from itsdangerous import BadSignature

from core.common.exceptions import APIError

from takumi import slack
from takumi.models import Campaign, Post
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.signers import task_signer
from takumi.tasks.instagram_metadata import refresh_mention_ig_metadata

from .blueprint import webhooks

__all__: List = []


@webhooks.route("/influencers/untagged", methods=["POST"])
def influencers_slack_untagged():
    token = request.json.get("token", "") if request.json else ""
    try:
        task_signer.unsign(token)
    except BadSignature:
        raise APIError("Token Error", 403)
    slack.influencer_untagged()
    return ""


@webhooks.route("/influencers/daily", methods=["POST"])
def influencers_slack_daily_report():
    token = request.json.get("token", "") if request.json else ""
    try:
        task_signer.unsign(token)
    except BadSignature:
        raise APIError("Token Error", 403)
    slack.influencer_report()
    return ""


@webhooks.route("/brands/daily", methods=["POST"])
def brands_post_mention_daily_instagram_info():
    token = request.json.get("token", "") if request.json else ""
    try:
        task_signer.unsign(token)
    except BadSignature:
        raise APIError("Token Error", 403)

    two_months_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(weeks=8)
    posts = Post.query.join(Campaign).filter(
        Post.created > two_months_ago,
        Campaign.state.in_([CAMPAIGN_STATES.LAUNCHED, CAMPAIGN_STATES.COMPLETED]),
    )

    for mention in list({p.mention for p in posts if p.mention is not None}):
        refresh_mention_ig_metadata.delay(mention)
    return ""


@webhooks.route("/facebook_webhooks", methods=["GET", "POST"])
def facebook_webhooks():
    if request.method == "GET":
        hub_mode = request.args["hub.mode"]
        hub_challenge = request.args["hub.challenge"]
        hub_verify_token = request.args["hub.verify_token"]
        if (
            hub_mode == "subscribe"
            and hub_verify_token == os.environ["FACEBOOK_CALLBACK_VERIFY_TOKEN"]
        ):
            return hub_challenge

    if request.method == "POST":
        slack.notify_debug("FACEBOOK_HOOK: " + str(request.json))
        return ""
