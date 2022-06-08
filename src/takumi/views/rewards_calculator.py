from flask import abort, jsonify, request
from flask_cors import cross_origin

from .blueprint import api

REWARD_PER_1000 = 3.25
MIN_REWARD = 50


def _round(num):
    return int(int(float(num) / 10) * 10)


def get_monthly_reward(followers, per_week):
    """For marketing purposes. Used by our takumi.com site for a widget that
    helps users understand their expected income if they participate as
    influencers on the platform.

    """
    per_month = float(per_week) / 7 * 30
    reward_per_month = float(followers) / 1000 * REWARD_PER_1000 * per_month
    min_reward = MIN_REWARD * per_month
    return [
        _round(max(min_reward, reward_per_month * 0.5)),
        _round(max(min_reward, reward_per_month * 1.5)),
    ]


@api.route("/rewards", methods=["POST"])
@cross_origin()
def rewards():
    try:
        followers = min(200_000, max(1000, request.json["followers"]))
        per_week = min(4, max(1, request.json["per_week"]))
    except KeyError:
        abort()
    return jsonify(reward_range=get_monthly_reward(followers, per_week))
