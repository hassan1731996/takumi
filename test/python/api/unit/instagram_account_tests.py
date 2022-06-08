import mock

from takumi.ig.instascrape import NotFound
from takumi.instagram_account import (
    create_or_get_instagram_account_by_username,
    fetch_instagram_account_by_username,
    refresh_instagram_account,
)


def test_create_or_get_instagram_account_by_username_if_account_found(client, instagram_account):
    with mock.patch(
        "takumi.models.instagram_account.InstagramAccount.by_username",
        return_value=instagram_account,
    ):
        account = create_or_get_instagram_account_by_username(instagram_account.ig_username)
    assert account == instagram_account


def test_create_or_get_instagram_account_by_username_creates_account_from_scrape_if_doesnt_exists(
    client, monkeypatch
):
    profile = {"id": "123", "username": "username"}
    monkeypatch.setattr("takumi.instagram_account.instascrape.get_user", lambda _: profile)
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.first", lambda *args: None)

    with mock.patch("takumi.instagram_account.InstagramAccount.by_username", return_value=None):
        with mock.patch(
            "takumi.instagram_account.InstagramAccount.create_from_user_data"
        ) as mock_create:
            create_or_get_instagram_account_by_username("username")

    mock_create.assert_called_with(profile)


def test_create_or_get_instagram_account_by_username_updates_account_if_found_by_id_but_not_username(
    client, instagram_account, monkeypatch
):
    profile = {"id": "123", "username": "username"}
    monkeypatch.setattr("takumi.instagram_account.instascrape.get_user", lambda _: profile)
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.first", lambda *args: instagram_account)

    with mock.patch("takumi.instagram_account.InstagramAccount.by_username", return_value=None):
        with mock.patch(
            "takumi.instagram_account.set_instagram_account_username"
        ) as mock_update_username:
            account = create_or_get_instagram_account_by_username("username")

    mock_update_username.assert_called_with(instagram_account, profile["username"])
    assert account == instagram_account


def test_refresh_instagram_account_updates_username_if_changed(
    client, instagram_account, monkeypatch, influencer
):
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr(
        "takumi.services.InstagramAccountService.get_followers_history_anomalies", lambda _: []
    )
    monkeypatch.setattr("takumi.instagram_account.calculate_engagement_median", lambda _: 1.0)
    monkeypatch.setattr("takumi.instagram_account.InstagramAccountLog", lambda _: mock.Mock())

    mock_profile = {"username": "new_username"}
    monkeypatch.setattr(
        "takumi.instagram_account.instascrape.get_user_by_instagram_account",
        lambda *args, **kwargs: mock_profile,
    )
    with mock.patch("takumi.instagram_account.set_instagram_account_username") as mock_set_username:
        refresh_instagram_account(instagram_account)
    mock_set_username.assert_called_with(instagram_account, "new_username")

    mock_profile = {"username": instagram_account.ig_username}
    monkeypatch.setattr(
        "takumi.instagram_account.instascrape.get_user_by_instagram_account",
        lambda *args, **kwargs: mock_profile,
    )
    with mock.patch("takumi.instagram_account.set_instagram_account_username") as mock_set_username:
        refresh_instagram_account(instagram_account)
    mock_set_username.assert_not_called()


def test_fetch_instagram_account_by_username_returns_none_if_not_on_instagram(app, monkeypatch):
    monkeypatch.setattr(
        "takumi.instagram_account.instascrape.get_user", mock.Mock(side_effect=[NotFound])
    )
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.first", lambda *args: None)

    account = fetch_instagram_account_by_username("username")

    assert account is None


def test_fetch_instagram_account_by_username_returns_account_if_scraped_and_found_by_id(
    app, instagram_account, monkeypatch
):
    mock_profile = {"id": "user_id", "username": instagram_account.ig_username}
    monkeypatch.setattr(
        "takumi.instagram_account.instascrape.get_user", mock.Mock(return_value=mock_profile)
    )
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.first", lambda *args: instagram_account)

    with mock.patch("takumi.instagram_account.set_instagram_account_username") as mock_set_username:
        account = fetch_instagram_account_by_username("username")

    assert not mock_set_username.called
    assert account == instagram_account


def test_fetch_instagram_account_by_username_updates_username_if_different_from_scrape(
    app, instagram_account, monkeypatch
):
    mock_profile = {"id": "user_id", "username": "new_username"}
    monkeypatch.setattr(
        "takumi.instagram_account.instascrape.get_user", mock.Mock(return_value=mock_profile)
    )
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.first", lambda *args: instagram_account)

    with mock.patch("takumi.instagram_account.set_instagram_account_username") as mock_set_username:
        account = fetch_instagram_account_by_username("username")

    assert mock_set_username.called
    mock_set_username.assert_called_with(instagram_account, "new_username")
    assert account == instagram_account


class MockInstagramAPI:
    def get_profile(self):
        return {
            "biography": "a",
            "id": "123",
            "ig_id": 321,
            "followers_count": 1000,
            "follows_count": 500,
            "media_count": 20,
            "name": "Valtýr Björn",
            "profile_picture_url": "http://valtyr.com/valtyr.jpg",
            "username": "valtyr",
            "website": "https://valtyr.com",
        }

    def get_medias(self):
        return []


def test_refresh_instagram_account_with_instagram_api(monkeypatch, instagram_account, influencer):
    monkeypatch.setattr("takumi.models.influencer.Influencer.instagram_api", MockInstagramAPI())
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.first", lambda *args: instagram_account)
    monkeypatch.setattr("sqlalchemy.orm.query.Query.all", lambda *args: [])
    refresh_instagram_account(instagram_account)


def test_refresh_instagram_account_with_instascrape(monkeypatch, instagram_account, influencer):
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.first", lambda *args: instagram_account)
    monkeypatch.setattr("sqlalchemy.orm.query.Query.all", lambda *args: [])

    mock_profile = {
        "media_count": 20,
        "id": "123",
        "full_name": "Valtýr Björn",
        "following": 500,
        "external_url": "https://www.valtyr.com/",
        "biography": "a",
        "is_verified": False,
        "email": "valtyr@valtyr.com",
        "boosted": False,
        "username": "valtyr",
        "is_private": False,
        "is_business_account": True,
        "followers": 1000,
        "profile_picture": "http://valtyr.com/valtyr.jpg",
        "media": {"nodes": []},
    }

    monkeypatch.setattr(
        "takumi.instagram_account.instascrape.get_user_by_instagram_account",
        mock.Mock(return_value=mock_profile),
    )

    refresh_instagram_account(instagram_account)
