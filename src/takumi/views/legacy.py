import datetime as dt

from flask import jsonify, request

from takumi.auth import min_version_required
from takumi.gql.query.media import MediaQuery
from takumi.models import Region
from takumi.signers import url_signer

from .blueprint import api

ITEMS_PER_PAGE = 30
DEFAULT_GIG_DURATION = dt.timedelta(days=3)


PREVIEW_TOKEN_TIMEOUT = 60 * 60


def get_preview_token():
    token = request.args.get("token")
    if token:
        return url_signer.loads(token, salt="preview_campaign", max_age=PREVIEW_TOKEN_TIMEOUT)
    return None


def get_top_level_regions():
    return Region.query.filter(Region.path == None, Region.supported == True)  # noqa: E711


@api.route("/campaigns/sample_medias", methods=["GET"])
def get_sample_medias():
    sample_medias = MediaQuery().resolve_sample_medias("info")
    return jsonify({"medias": sample_medias}), 200


@api.route("/campaigns/<uuid:campaign_id>", methods=["GET"])
@min_version_required
def deprecated_view(*args, **kwargs):
    return jsonify({})
