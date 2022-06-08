# encoding=utf-8
import mock
import pytest
from flask import url_for

from core.common.exceptions import APIError

from takumi.error_codes import (
    ALREADY_VERIFIED_ERROR_CODE,
    MEDIA_NO_CODE_FOUND_ERROR_CODE,
    MEDIA_NOT_FOUND_ERROR_CODE,
    MEDIA_OWNER_MISMATCH_ERROR_CODE,
)
from takumi.models import Influencer, InstagramAccount
from takumi.views.signup import (
    find_token_comment_for_media,
    get_scraped_ig_info,
    verify_media_for_account,
)

MOCK_SCRAPE = {
    "followers": 12345,
    "username": "username",
    "full_name": "influencer name",
    "id": 123_123_123,
    "is_private": False,
    "media_count": 123,
    "profile_picture": "http://example.com/profile.jpg",
}


class RedisMock:
    values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, exp, value):
        self.values[key] = value

    def delete(self, key):
        del self.values[key]


def test_signup_start_verification(client, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    with mock.patch("random.choice", side_effect=lambda seq: seq[0]):
        with mock.patch("takumi.views.signup.get_human_random_string", return_value="token"):
            with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_get:
                mock_get.return_value = None
                with mock.patch("sqlalchemy.orm.session.Session.add") as mock_add:
                    response = client.post(
                        url_for("api.start_verification"), data={"username": "jokull"}
                    )
    assert response.status_code == 201
    assert mock_add.called
    account = mock_add.call_args[0][0]
    assert account.ig_media_id == "1474136368534964793"
    assert account.verified is False
    assert account.ig_username == "jokull"  # from autouse fixture
    assert account.ig_biography == "Founder of @TakumiHQ"
    assert account.followers
    assert account.media_count
    assert response.json["token"] == "token"
    assert response.json["post"]["id"] == "1474136368534964793"
    assert "image_url" in response.json["post"]
    assert "link" in response.json["post"]


def test_signup_start_verification_fails_if_account_exists_and_is_verified(
    client, influencer, instagram_account, influencer_user, monkeypatch
):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *_: None)

    instagram_account.verified = True
    instagram_account.influencer = Influencer(user=influencer_user, is_signed_up=True)
    with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_get:
        mock_get.return_value = instagram_account
        with mock.patch("sqlalchemy.orm.session.Session.add"):
            response = client.post(url_for("api.start_verification"), data={"username": "jokull"})
    assert response.status_code == 403
    assert response.json["error"]["code"] == ALREADY_VERIFIED_ERROR_CODE


def test_signup_start_verification_works_if_account_exists_but_email_login_doesnt(
    client, instagram_account, monkeypatch
):
    mock_profile = {"id": instagram_account.ig_user_id, "username": instagram_account.ig_username}
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("takumi.views.signup.get_scraped_ig_info", lambda _: mock_profile)
    instagram_account.verified = True
    instagram_account.influencer = Influencer(is_signed_up=False)
    with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_get:
        mock_get.return_value = instagram_account
        with mock.patch("sqlalchemy.orm.session.Session.add"):
            response = client.post(url_for("api.start_verification"), data={"username": "jokull"})
    assert response.status_code == 200


def test_signup_start_verification_succeeds_if_account_exists_but_is_not_an_influencer(
    client, instagram_account, monkeypatch
):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    instagram_account.verified = True
    with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_get:
        mock_get.return_value = instagram_account
        with mock.patch("sqlalchemy.orm.session.Session.add"):
            response = client.post(url_for("api.start_verification"), data={"username": "jokull"})
    assert response.status_code == 200


def test_signup_start_verification_succeeds_using_email(client, monkeypatch):
    response = client.post(url_for("api.start_verification"), data={"username": "test@test.com"})
    assert response.status_code == 201


def test_signup_start_verification_fails_if_no_media(client, instagram_account, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    with mock.patch("takumi.views.signup.instascrape") as mock_instascrape:
        mock_instascrape.get_user_media.return_value = {"data": []}
        with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_get:
            mock_get.return_value = instagram_account
            with mock.patch("sqlalchemy.orm.session.Session.add"):
                response = client.post(
                    url_for("api.start_verification"), data={"username": "jokull"}
                )
        assert response.status_code == 403
        assert response.json["error"]["message"] == "No images found for account"


def test_signup_start_verification_sets_token_and_media_if_account_exists(
    client, instagram_account, monkeypatch
):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    old_token = instagram_account.token
    old_ig_media_id = instagram_account.ig_media_id

    with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_get:
        instagram_account.verified = False
        mock_get.return_value = instagram_account
        with mock.patch("sqlalchemy.orm.session.Session.add") as mock_add:
            response = client.post(url_for("api.start_verification"), data={"username": "jokull"})
    assert response.status_code == 200
    account = mock_add.call_args[0][0]
    assert account.ig_media_id != old_ig_media_id
    assert account.token != old_token
    assert account.id == instagram_account.id


def test_find_token_comment_for_media_found():
    assert find_token_comment_for_media(
        {"comments": {"nodes": [{"user_id": "bar", "text": "foo"}]}, "caption": ""},
        InstagramAccount(token="FOO", ig_user_id="bar"),
    )


def test_find_token_comment_for_media_right_token_wrong_user():
    assert not find_token_comment_for_media(
        {"comments": {"nodes": [{"user_id": "not_bar", "text": "foo"}]}, "caption": ""},
        InstagramAccount(token="FOO", ig_user_id="bar"),
    )


def test_find_token_comment_for_media_wrong_token_right_user():
    assert not find_token_comment_for_media(
        {"comments": {"nodes": [{"user_id": "bar", "text": "foo"}]}, "caption": ""},
        InstagramAccount(token="NOT_FOO", ig_user_id="bar"),
    )


def test_find_token_comment_for_media_token_in_caption():
    assert find_token_comment_for_media(
        {"comments": {"nodes": []}, "caption": "foo"},
        InstagramAccount(token="FOO", ig_user_id="bar"),
    )


def test_verify_media_for_account_media_not_found():
    with pytest.raises(APIError) as exc:
        verify_media_for_account(None, InstagramAccount())
    assert exc.value.error_code == MEDIA_NOT_FOUND_ERROR_CODE


def test_verify_media_for_account_different_user():
    with pytest.raises(APIError) as exc:
        verify_media_for_account({"owner": {"id": "foo"}}, InstagramAccount(ig_user_id="bar"))
    assert exc.value.error_code == MEDIA_OWNER_MISMATCH_ERROR_CODE


def test_verify_media_for_account_no_token_found():
    with pytest.raises(APIError) as exc:
        verify_media_for_account(
            {"owner": {"id": "foo"}, "comments": {"nodes": []}, "caption": ""},
            InstagramAccount(token="FOO", ig_user_id="foo"),
        )
    assert exc.value.error_code == MEDIA_NO_CODE_FOUND_ERROR_CODE


def test_verify_media_for_account_success():
    assert None is verify_media_for_account(
        {"owner": {"id": "bar"}, "comments": {"nodes": [{"user_id": "bar", "text": "foo"}]}},
        InstagramAccount(token="FOO", ig_user_id="bar"),
    )


def test_signup_verify_instagram_account_verified(client, instagram_account, monkeypatch):
    instagram_account.token = "FOO"
    instagram_account.ig_username = "bar"
    instagram_account.ig_media_id = "foo"
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("takumi.views.signup.verify_media_for_account", lambda m, a: True)
    with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_get:
        mock_get.return_value = instagram_account
        with mock.patch("sqlalchemy.orm.session.Session.add") as mock_add:
            response = client.post(
                url_for("api.verify_instagram_account"),
                data={"ig_media_id": "foo", "ig_user_id": "bar"},
            )
    assert response.status_code == 200
    assert response.json["verified"] == True
    assert mock_add.call_args[0][0] == instagram_account


def test_get_instagram_user_not_signed_up(client):
    with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_first:
        mock_first.return_value = None
        with mock.patch("takumi.views.signup.get_scraped_ig_info") as mock_get_scraped_ig_info:
            mock_get_scraped_ig_info.return_value = MOCK_SCRAPE
            response = client.get(url_for("api.get_instagram_user", username="foo"))
    assert response.status_code == 200
    assert not response.json["verified"]
    assert mock_get_scraped_ig_info.called
    assert mock_get_scraped_ig_info.call_args[0][0] == "foo"


def test_get_instagram_user_returns_new_unfinished_signup(client, instagram_account, influencer):
    instagram_account.verified = True
    influencer.instagram_account = None
    assert not instagram_account.influencer

    with mock.patch("flask_sqlalchemy.BaseQuery.first", return_value=instagram_account):
        with mock.patch("takumi.views.signup.get_scraped_ig_info") as mock_get_scraped_ig_info:
            mock_get_scraped_ig_info.return_value = MOCK_SCRAPE
            response = client.get(
                url_for("api.get_instagram_user", username=instagram_account.ig_username)
            )
    assert mock_get_scraped_ig_info.called
    assert not response.json["verified"]


def test_get_instagram_user_returns_not_verified_for_verified_but_unfinished_signup(
    client, instagram_account, influencer, monkeypatch
):
    instagram_account.verified = True
    influencer.is_signed_up = False
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_first:
        mock_first.return_value = instagram_account
        with mock.patch("takumi.views.signup.get_scraped_ig_info") as mock_get_scraped_ig_info:
            mock_get_scraped_ig_info.return_value = MOCK_SCRAPE
            response = client.get(
                url_for("api.get_instagram_user", username=instagram_account.ig_username)
            )
    assert mock_get_scraped_ig_info.called
    assert not response.json["verified"]


def test_get_instagram_user_returns_verified_for_finished_signup(
    client, instagram_account, influencer, monkeypatch
):
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    instagram_account.verified = True
    instagram_account.influencer = influencer
    with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_first:
        with mock.patch("takumi.views.signup.get_scraped_ig_info") as mock_get_scraped_ig_info:
            mock_get_scraped_ig_info.return_value = {
                "id": instagram_account.ig_user_id,
                "username": instagram_account.ig_username,
            }
            mock_first.return_value = instagram_account
            response = client.get(
                url_for("api.get_instagram_user", username=instagram_account.ig_username)
            )
    assert response.json["id"] == instagram_account.ig_user_id
    assert response.json["verified"]


def test_get_instagram_user_replaces_username_if_changed(
    client, instagram_account, influencer, monkeypatch
):
    """Old influencer, new username which is not taken"""
    new_username = "new_username"
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)

    assert instagram_account.ig_username != new_username
    instagram_account.verified = True

    with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_first:
        with mock.patch("takumi.views.signup.get_scraped_ig_info") as mock_get_scraped_ig_info:
            mock_get_scraped_ig_info.return_value = {
                "id": instagram_account.ig_user_id,
                "username": new_username,
            }
            mock_first.return_value = instagram_account
            response = client.get(url_for("api.get_instagram_user", username=new_username))

    assert response.status_code == 200
    assert response.json["username"] == new_username
    assert response.json["verified"] == True


def test_get_scraped_ig_info_schedules_username_update_on_old_account_if_found(
    client, influencer, instagram_account, monkeypatch
):
    instagram_account.ig_user_id = 456

    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *_: None)
    monkeypatch.setattr("takumi.views.signup.instascrape.get_user", lambda *_, **__: {"id": 123})
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.first", lambda *_: instagram_account)

    with mock.patch("takumi.views.signup.instagram_account_tasks") as mock_tasks:
        get_scraped_ig_info("username")

    assert mock_tasks.instagram_account_new_username.delay.called


def test_get_scraped_ig_info_doesnt_schedule_username_update_if_account_with_same_id_found(
    client, monkeypatch
):
    with mock.patch("takumi.views.signup.instascrape") as mock_instascrape:
        mock_instascrape.get_user.return_value = {"id": 123}
        with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_first:
            with mock.patch("takumi.views.signup.instagram_account_tasks") as mock_tasks:
                mock_ig_account = mock.Mock()
                mock_ig_account.ig_user_id = 123  # ID the same
                mock_first.return_value = mock_ig_account

                get_scraped_ig_info("username")

    assert not mock_tasks.instagram_account_new_username.delay.called


def test_get_scraped_ig_info_doesnt_schedule_username_update_if_no_old_account_found(
    client, monkeypatch
):
    with mock.patch("takumi.views.signup.instascrape") as mock_instascrape:
        mock_instascrape.get_user.return_value = {"id": 123}
        with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_first:
            with mock.patch("takumi.views.signup.instagram_account_tasks") as mock_tasks:
                mock_first.return_value = None

                get_scraped_ig_info("username")

    assert not mock_tasks.instagram_account_new_username.delay.called


def test_get_scraped_ig_info_strips_spaces_and_at_symbol_from_usernames(client, instagram_account):
    with mock.patch("flask_sqlalchemy.BaseQuery.first") as mock_first:
        mock_first.return_value = None
        with mock.patch("takumi.views.signup.instascrape") as mock_instascrape:
            get_scraped_ig_info("@mpersand ")
    assert mock_instascrape.get_user.called_with("mpersand")


def test_get_scraped_ig_info_doesnt_schedule_username_change_on_user_that_didnt_finish_signup(
    client, instagram_account, monkeypatch
):
    username = instagram_account.ig_username

    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *_: None)
    monkeypatch.setattr("takumi.views.signup.instascrape.get_user", lambda *_, **__: {"id": 123})
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.first", lambda *_: instagram_account)

    with mock.patch("takumi.views.signup.instagram_account_tasks") as mock_tasks:
        get_scraped_ig_info("username")

    assert not mock_tasks.instagram_account_new_username.delay.called
    assert instagram_account.ig_username != username
