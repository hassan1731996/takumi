import datetime as dt

from takumi.models import InstagramAccountEvent
from takumi.services.instagram_account import InstagramAccountService


def test_instagram_account_service_get_by_id(db_instagram_account):
    instagram_account = InstagramAccountService.get_by_id(db_instagram_account.id)

    assert instagram_account == db_instagram_account


def test_instagram_account_service_get_by_username(db_instagram_account):
    instagram_account = InstagramAccountService.get_by_username(db_instagram_account.ig_username)

    assert instagram_account == db_instagram_account


def test_instagram_account_service_get_followers_history(db_session, db_instagram_account):
    # Arrange
    now = dt.datetime.now(dt.timezone.utc)
    min_follower_event = InstagramAccountEvent(
        type="instagram-update",
        event={"followers": 100},
        instagram_account_id=db_instagram_account.id,
        created=now,
    )
    more_follower_event = InstagramAccountEvent(
        type="instagram-update",
        event={"followers": 500},
        instagram_account_id=db_instagram_account.id,
        created=now,
    )
    max_follower_event = InstagramAccountEvent(
        type="instagram-update",
        event={"followers": 1000},
        instagram_account_id=db_instagram_account.id,
        created=now,
    )
    db_session.add(min_follower_event)
    db_session.add(more_follower_event)
    db_session.add(max_follower_event)
    db_session.commit()

    # Act
    followers_history = InstagramAccountService.get_followers_history(db_instagram_account.id).all()

    # Assert
    assert followers_history == [(now.date(), 100, 1000)]


def test_instagram_account_service_create_instagram_account(db_session):
    profile = dict(
        id="id",
        username="username",
        is_private=False,
        biography="biography",
        followers=1000,
        following=10,
        media_count=100,
        profile_picture="http://profile.picture",
    )
    instagram_account = InstagramAccountService.create_instagram_account(profile)

    assert instagram_account.ig_user_id == "id"
    assert instagram_account.ig_username == "username"
    assert instagram_account.ig_is_private is False
    assert instagram_account.ig_biography == "biography"
    assert instagram_account.ig_media_id == ""
    assert instagram_account.token == ""
    assert instagram_account.followers == 1000
    assert instagram_account.follows == 10
    assert instagram_account.media_count == 100
    assert instagram_account.verified is False


def test_instagram_account_dismiss_followers_anomalies(app, db_instagram_account, db_session):
    db_instagram_account.followers_history_anomalies = [
        {"date": "2000-01-01", "follower_increase": 0, "anomaly_factor": 0, "ignore": False}
    ]
    db_session.commit()
    with InstagramAccountService(db_instagram_account) as srv:
        srv.dismiss_followers_anomalies()
    assert db_instagram_account.followers_history_anomalies[0]["ignore"]
