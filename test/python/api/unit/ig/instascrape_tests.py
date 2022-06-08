from json import JSONDecodeError

import mock
import pytest

from takumi.extensions import instascrape
from takumi.ig.instascrape import InstascrapeError, NotFound


def test_instascrape_get_user_by_instagram_account_not_found(instagram_account):
    with mock.patch.object(instascrape, "get_user", side_effect=[NotFound]):
        with mock.patch.object(instascrape, "get_user_by_id", side_effect=[NotFound]):
            with pytest.raises(NotFound):
                instascrape.get_user_by_instagram_account(instagram_account)


def test_instascrape_get_user_by_instagram_account_username_found_id_match(instagram_account):
    with mock.patch.object(
        instascrape, "get_user", return_value={"id": instagram_account.ig_user_id}
    ):
        profile = instascrape.get_user_by_instagram_account(instagram_account)

    assert profile["id"] == instagram_account.ig_user_id


def test_instascrape_get_user_by_instagram_account_username_found_id_mismatch(instagram_account):
    with mock.patch.object(instascrape, "get_user", return_value={"id": "invalid_id"}):
        with mock.patch.object(
            instascrape, "get_user_by_id", return_value={"id": instagram_account.ig_user_id}
        ):
            profile = instascrape.get_user_by_instagram_account(instagram_account)

    assert profile["id"] == instagram_account.ig_user_id


def test_instascrape_get_user_by_instagram_account_username_not_found_but_it_found(
    instagram_account,
):
    with mock.patch.object(instascrape, "get_user", side_effect=[NotFound]):
        with mock.patch.object(
            instascrape, "get_user_by_id", return_value={"id": instagram_account.ig_user_id}
        ):
            profile = instascrape.get_user_by_instagram_account(instagram_account)

    assert profile["id"] == instagram_account.ig_user_id


def test_instascrape_get_json_decode_error_reports_to_sentry(app):
    class BrokenJsonResponse:
        status_code = 500

        def json(self):
            raise JSONDecodeError("fake", "", 0)

    with pytest.raises(InstascrapeError):
        with mock.patch("takumi.ig.instascrape.requests.get", return_value=BrokenJsonResponse()):
            with mock.patch("takumi.ig.instascrape.capture_exception") as mock_capture_exception:
                instascrape._get("/mock/me")
    assert mock_capture_exception.called


def test_instascrape_get_no_valid_json_unknown_error_reports_to_sentry(app):
    class InvalidJsonResponse:
        status_code = 500

        def json(self):
            return {}

    with pytest.raises(InstascrapeError):
        with mock.patch("takumi.ig.instascrape.requests.get", return_value=InvalidJsonResponse()):
            with mock.patch("takumi.ig.instascrape.capture_exception") as mock_capture_exception:
                instascrape._get("/mock/me")
    assert mock_capture_exception.called


def test_instascrape_get_post_by_caption_returns_closest_match(app):
    posts = [
        {"caption": "Bunnies are my favourite animals"},
        {"caption": "Have you seen the rain?"},
        {"caption": "Takumi is the best platform"},
        {"caption": "Takumi is the worst platform"},
        {"caption": "Indahash is the best platform"},
    ]

    with mock.patch.object(instascrape, "get_user_media", return_value={"data": posts}):
        result = instascrape.get_post_by_caption("username", "Takumi is best", accuracy=0.5)

    assert result == {"caption": "Takumi is the best platform"}


def test_instascrape_get_post_by_caption_returns_closest_match_with_high_accuracy(app):
    posts = [
        {"caption": "Bunnies are my favourite animals"},
        {"caption": "Have you seen the rain?"},
        {"caption": "Takumi is the best platform"},
        {"caption": "Takumi is the worst platform"},
        {"caption": "Indahash is the best platform"},
    ]

    with mock.patch.object(instascrape, "get_user_media", return_value={"data": posts}):
        not_accurate_enough = instascrape.get_post_by_caption(
            "username", "Takumi is best", accuracy=0.95
        )
        accurate_enough = instascrape.get_post_by_caption(
            "username", "Takumi is the best platform", accuracy=0.95
        )

    assert not_accurate_enough is None
    assert accurate_enough == {"caption": "Takumi is the best platform"}


def test_instascrape_get_post_by_caption_when_no_media(app):
    with mock.patch.object(instascrape, "get_user_media", return_value={"data": []}):
        result = instascrape.get_post_by_caption("username", "caption")

    assert result is None
