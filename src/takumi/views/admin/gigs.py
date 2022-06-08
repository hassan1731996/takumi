from urllib.parse import urlparse

from flask import jsonify, request
from marshmallow import Schema, fields

from takumi.models import Campaign
from takumi.services import CampaignService, GigService
from takumi.utils.json import get_valid_json
from takumi.views.blueprint import api


class GigMediaUrlsSchema(Schema):
    report_token = fields.UUID(required=True)


@api.route("/gigs/<uuid:gig_id>/media_urls", methods=["POST"])
def get_gig_media_urls(gig_id):
    """
    Get media urls on this format:
    {
        username 1: [
            media 1,
            media 2,
            ...
        ]
    }
    """
    gig = GigService.get_by_id(gig_id)
    if gig is None:
        return jsonify({"error": "Gig not found"}), 404

    form = get_valid_json(GigMediaUrlsSchema(), request)
    campaign = CampaignService.get_by_report_token(form["report_token"])
    if campaign is None:
        return jsonify({"error": "Campaign not found"}), 404

    if gig.post.campaign != campaign:
        return jsonify({"error": "Campaign report token does not match gig id"}), 404

    media_urls = []
    if gig.instagram_post:
        media_urls = [urlparse(media.url).path for media in gig.instagram_post.media]
    elif gig.instagram_story:
        media_urls = [urlparse(media.url).path for media in gig.instagram_story.media]
    return jsonify({gig.offer.influencer.username: media_urls})


@api.route("/gigs/<uuid:gig_id>/submission_urls", methods=["POST"])
def get_gig_submission_urls(gig_id):
    """
    Get submission media urls on this format:
    {
        username 1: [
            media 1,
            media 2,
            ...
        ]
    }
    """
    gig = GigService.get_by_id(gig_id)
    if gig is None:
        return jsonify({"error": "Gig not found"}), 404

    if "submissions_token" not in request.json:
        return jsonify({"error": "Campaign not found"}), 404
    submissions_token = request.json["submissions_token"]

    campaign = Campaign.query.filter(Campaign.submissions_token == submissions_token).one_or_none()

    if campaign is None:
        return jsonify({"error": "Campaign not found"}), 404

    if gig.post.campaign != campaign:
        return jsonify({"error": "Campaign report token does not match gig id"}), 404

    media_urls = []
    if gig.submission:
        media_urls = [urlparse(media.url).path for media in gig.submission.media]
    return jsonify({gig.offer.influencer.username: media_urls})
