# encoding=utf-8

from flask import url_for

from takumi.views.rewards_calculator import get_monthly_reward


def test_rewards_endpoint(client):
    response = client.post(url_for("api.rewards"), data={"per_week": 2, "followers": 1000})
    assert response.status_code == 200


def test_rewards_endpoint_clamp_up(client):
    response_base = client.post(
        url_for("api.rewards"), data={"per_week": 1, "followers": 1000}
    ).json
    response_clamped = client.post(
        url_for("api.rewards"), data={"per_week": 0, "followers": 0}
    ).json
    assert response_base == response_clamped


def test_rewards_endpoint_clamp_down(client):
    response_base = client.post(
        url_for("api.rewards"), data={"per_week": 4, "followers": 200_000}
    ).json
    response_clamped = client.post(
        url_for("api.rewards"), data={"per_week": 5, "followers": 300_000}
    ).json
    assert response_base == response_clamped


def test_get_monthly_reward_base_case():
    assert get_monthly_reward(1000, 1) == [210, 210]
    assert get_monthly_reward(0, 1) == [210, 210]


def test_get_monthly_reward_reach_influencer():
    assert get_monthly_reward(11000, 1) == [210, 220]
    assert get_monthly_reward(11000, 2) == [420, 450]


def test_get_monthly_reward_no_gigs():
    assert get_monthly_reward(1000, 0) == [0, 0]


def test_get_monthly_reward_huge_reach():
    assert get_monthly_reward(200_000, 2) == [2780, 8350]
