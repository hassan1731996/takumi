import datetime as dt

import mock
import pytest
from freezegun import freeze_time

from takumi.models.influencer import STATES as INFLUENCER_STATES
from takumi.models.market import us_market
from takumi.models.payment import STATES as PAYMENT_STATES
from takumi.notifications.exceptions import NotificationException
from takumi.services.influencer import (
    DeletingInfluencerSoonerThanScheduledException,
    ForbiddenException,
    InfluencerAlreadyExistsException,
    InfluencerAlreadyScheduledForDeletionException,
    InfluencerEvent,
    InfluencerNotFound,
    InfluencerNotScheduledForDeletionException,
    InfluencerService,
    OfferEvent,
    SendInfluencerMessageError,
    ServiceException,
)


def test_influencer_service_get_by_id(db_influencer):
    influencer = InfluencerService.get_by_id(db_influencer.id)
    assert influencer == db_influencer


def test_influencer_service_get_by_username(db_influencer):
    influencer = InfluencerService.get_by_username(db_influencer.username)
    assert influencer == db_influencer


def test_influencer_service_get_influencer_events(db_session, db_influencer):
    # Arrange
    date_from = dt.datetime.now(dt.timezone.utc)
    date_to = date_from + dt.timedelta(hours=10)
    between_dates = date_from + dt.timedelta(hours=5)
    too_old_date = date_from - dt.timedelta(hours=1)
    too_young_date = date_to + dt.timedelta(hours=1)

    event = InfluencerEvent(
        type="correct type", created=between_dates, influencer_id=db_influencer.id
    )
    ignore_type = InfluencerEvent(
        type="ignored", created=between_dates, influencer_id=db_influencer.id
    )
    ignore_too_old = InfluencerEvent(
        type="correct type", created=too_old_date, influencer_id=db_influencer.id
    )
    ignore_too_young = InfluencerEvent(
        type="correct type", created=too_young_date, influencer_id=db_influencer.id
    )

    db_session.add_all([event, ignore_type, ignore_too_old, ignore_too_young])
    db_session.commit()

    # Act
    events = InfluencerService.get_influencer_events(
        db_influencer.id, ["correct type"], date_from, date_to
    ).all()

    # Assert
    assert len(events) == 1
    assert events[0][0] == between_dates
    assert events[0][1] == "correct type"


def test_influencer_service_get_offer_events(db_session, db_influencer, db_offer):
    # Arrange
    date_from = dt.datetime.now(dt.timezone.utc)
    date_to = date_from + dt.timedelta(hours=10)
    between_dates = date_from + dt.timedelta(hours=5)
    too_old_date = date_from - dt.timedelta(hours=1)
    too_young_date = date_to + dt.timedelta(hours=1)

    event = OfferEvent(type="type", created=between_dates, offer_id=db_offer.id)
    ignore_too_old = OfferEvent(type="type", created=too_old_date, offer_id=db_offer.id)
    ignore_too_young = OfferEvent(type="type", created=too_young_date, offer_id=db_offer.id)

    db_session.add_all([event, ignore_too_old, ignore_too_young])
    db_session.commit()

    # Act
    events = InfluencerService.get_offer_events(db_influencer.id, None, date_from, date_to).all()

    # Assert
    assert len(events) == 1
    assert events[0][0] == between_dates
    assert events[0][1] == "offer"
    assert events[0][2] == event.id


@pytest.mark.skip(
    reason="The method seems to be incomplete and is referencing Gig model instead of GigEvent. Revisit"
)
def test_influencer_service_get_gig_events():
    raise NotImplementedError()


def test_influencer_service_create_influencer(db_instagram_account, db_developer_user):
    influencer = InfluencerService.create_influencer(
        instagram_account=db_instagram_account, user=db_developer_user, is_signed_up=False
    )

    assert influencer.instagram_account == db_instagram_account
    assert influencer.user == db_developer_user
    assert influencer.is_signed_up is False


def test_influencer_service_create_prewarmed_influencer_fails_if_influencer_already_exists(
    db_influencer,
):
    with pytest.raises(InfluencerAlreadyExistsException) as exc:
        InfluencerService.create_prewarmed_influencer(db_influencer.username)

    assert (
        'Influencer with username "{}" already exists'.format(db_influencer.username)
        in exc.exconly()
    )


def test_influencer_service_create_prewarmed_influencer(db_session, monkeypatch):
    # Arrange
    profile = dict(
        id="id",
        username="username",
        full_name="full name",
        is_private=False,
        biography="biography",
        followers=1000,
        following=100,
        media_count=50,
        profile_picture="profile picture",
    )
    monkeypatch.setattr("takumi.services.influencer.instascrape.get_user", lambda *args: profile)

    # Act
    influencer = InfluencerService.create_prewarmed_influencer("new username")

    # Assert
    assert influencer.instagram_account.ig_user_id == "id"
    assert influencer.instagram_account.ig_username == "username"
    assert influencer.instagram_account.ig_is_private is False
    assert influencer.instagram_account.ig_biography == "biography"
    assert influencer.instagram_account.followers == 1000
    assert influencer.instagram_account.follows == 100
    assert influencer.instagram_account.media_count == 50
    assert influencer.instagram_account.profile_picture == "profile picture"
    assert influencer.user.full_name == "full name"
    assert influencer.user.role_name == "influencer"
    assert influencer.is_signed_up is False


@freeze_time(dt.datetime(2016, 1, 10, 0, 0))
def test_influencer_service_schedule_deletion_success(db_influencer, monkeypatch):
    # Arrange
    monkeypatch.setattr("takumi.tasks.influencer.schedule_deletion", lambda *args: None)
    assert db_influencer.deletion_date is None
    twenty_four_hours_later = dt.datetime(2016, 1, 11, 0, 0, tzinfo=dt.timezone.utc)

    # Act
    InfluencerService(db_influencer).schedule_deletion()

    # Assert
    assert db_influencer.deletion_date == twenty_four_hours_later


def test_influencer_service_schedule_deletion_fails_if_already_scheduled(
    db_influencer, monkeypatch
):
    monkeypatch.setattr("takumi.tasks.influencer.schedule_deletion", lambda *args: None)
    InfluencerService(db_influencer).schedule_deletion()
    with pytest.raises(InfluencerAlreadyScheduledForDeletionException):
        InfluencerService(db_influencer).schedule_deletion()


def test_influencer_service_cancel_schedule_deletion_success(db_influencer, monkeypatch):
    # Assert
    monkeypatch.setattr("takumi.tasks.influencer.schedule_deletion", lambda *args: None)
    monkeypatch.setattr("takumi.tasks.influencer.clear_deletion", lambda *args: None)
    InfluencerService(db_influencer).schedule_deletion()
    assert db_influencer.deletion_date is not None

    # Act
    InfluencerService(db_influencer).cancel_scheduled_deletion()

    # Assert
    assert db_influencer.deletion_date is None


def test_influencer_service_cancel_schedule_deletion_fails_if_not_scheduled_for_deletion(
    db_influencer,
):
    # Assert
    assert db_influencer.deletion_date is None

    # Act & Assert
    with pytest.raises(InfluencerNotScheduledForDeletionException):
        InfluencerService(db_influencer).cancel_scheduled_deletion()


def test_influencer_service_delete_fails_if_too_soon(db_influencer):
    # Arrange
    db_influencer.deletion_date = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=24)

    # Act & Assert
    with pytest.raises(DeletingInfluencerSoonerThanScheduledException):
        InfluencerService(db_influencer).delete()


def test_influencer_service_delete_success(db_influencer, elasticsearch):
    # Arrange
    db_influencer.deletion_date = dt.datetime.now(dt.timezone.utc)

    assert db_influencer.state != INFLUENCER_STATES.DISABLED
    assert "removed" not in db_influencer.user.full_name

    # Act
    InfluencerService(db_influencer).delete()

    # Assert
    assert db_influencer.state == INFLUENCER_STATES.DISABLED
    assert "removed" in db_influencer.user.full_name


def test_influencer_service_update_interests(db_influencer, db_interest):
    # Act
    with InfluencerService(db_influencer) as service:
        service.update_interests([db_interest.id])

    # Assert
    assert db_interest.id in db_influencer.interest_ids


def test_influencer_service_update_gender(db_influencer):
    assert db_influencer.user.gender != "male"
    with InfluencerService(db_influencer) as service:
        service.update_gender("male")

    assert db_influencer.user.gender == "male"


def test_influencer_service_update_birthday_success(db_influencer):
    birthday = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=365 * 19)  # 19 years old
    with InfluencerService(db_influencer) as service:
        service.update_birthday(birthday)

    assert db_influencer.user.birthday == birthday.date()


def test_influencer_service_update_target_region(db_influencer, db_region):
    assert db_influencer.target_region_id != db_region.id

    with InfluencerService(db_influencer) as service:
        service.update_target_region(db_region.id)

    assert db_influencer.target_region_id == db_region.id


def test_influencer_service_review_fails_if_influencer_not_in_new_state(db_influencer):
    db_influencer.state = "reviewed"

    with pytest.raises(ServiceException) as exc:
        InfluencerService(db_influencer).review()

    assert "Can't review a {} influencer".format(db_influencer.state) in exc.exconly()
    assert db_influencer.state == "reviewed"


def test_influencer_service_review_success(db_influencer):
    db_influencer.state = "new"

    with InfluencerService(db_influencer) as service:
        service.review()

    assert db_influencer.state == "reviewed"


def test_influencer_service_disable_fails_if_influencer_not_in_correct_state(db_influencer):
    db_influencer.state = "incorrect state"

    with pytest.raises(ServiceException) as exc:
        InfluencerService(db_influencer).disable("reason")

    assert "Can't disable a {} influencer".format(db_influencer.state) in exc.exconly()
    assert db_influencer.state == "incorrect state"


def test_influencer_service_disable_success(db_influencer):
    db_influencer.state = "new"

    with InfluencerService(db_influencer) as service:
        service.disable("reason")

    assert db_influencer.state == "disabled"
    assert db_influencer.disabled_reason == "reason"


def test_influencer_service_enable_fails_if_not_in_disabled_state(db_influencer):
    db_influencer.state = "incorrect state"

    with pytest.raises(ServiceException) as exc:
        InfluencerService(db_influencer).enable()

    assert "Can't enable a {} influencer".format(db_influencer.state) in exc.exconly()
    assert db_influencer.state == "incorrect state"


def test_influencer_service_enable_success(db_influencer):
    db_influencer.state = "disabled"
    db_influencer.disabled_reason = "reason"

    with InfluencerService(db_influencer) as service:
        service.enable()

    assert db_influencer.state == "reviewed"
    assert db_influencer.disabled_reason is None


def test_influencer_service_cooldown_fails_if_influencer_in_incorrect_state(db_influencer):
    db_influencer.state = "incorrect state"

    with pytest.raises(ServiceException) as exc:
        InfluencerService(db_influencer).cooldown(10)

    assert "Can't cooldown a {} influencer".format(db_influencer.state) in exc.exconly()
    assert db_influencer.state == "incorrect state"


@freeze_time(dt.datetime(2016, 1, 10, 0, 0))
def test_influencer_service_cooldown_success(db_influencer, monkeypatch):
    monkeypatch.setattr("takumi.tasks.influencer.clear_cooldown", lambda *args: None)
    monkeypatch.setattr("takumi.tasks.influencer.schedule_end_cooldown", lambda *args: None)
    db_influencer.state = "reviewed"

    with InfluencerService(db_influencer) as service:
        service.cooldown(10)

    assert db_influencer.state == "cooldown"
    assert db_influencer.cooldown_ends == dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=10)


def test_influencer_service_cancel_cooldown_fails_if_influencer_in_incorrect_state(db_influencer):
    db_influencer.state = "incorrect state"

    with pytest.raises(ServiceException) as exc:
        InfluencerService(db_influencer).cancel_cooldown()

    assert (
        "Can't cancel a cooldown for a {} influencer".format(db_influencer.state) in exc.exconly()
    )
    assert db_influencer.state == "incorrect state"


def test_influencer_service_cancel_cooldown_success(db_influencer, monkeypatch):
    monkeypatch.setattr("takumi.tasks.influencer.clear_cooldown", lambda *args: None)
    db_influencer.state = "cooldown"

    with InfluencerService(db_influencer) as service:
        service.cancel_cooldown()

    assert db_influencer.state == "reviewed"


def test_influencer_service_verify_fails_if_influencer_in_incorrect_state(db_influencer):
    db_influencer.state = "incorrect state"

    with pytest.raises(ServiceException) as exc:
        InfluencerService(db_influencer).verify()

    assert "Can't verify a {} influencer".format(db_influencer.state) in exc.exconly()
    assert db_influencer.state == "incorrect state"


def test_influencer_service_verify_success(db_influencer):
    db_influencer.state = "reviewed"

    with InfluencerService(db_influencer) as service:
        service.verify()

    assert db_influencer.state == "verified"


def test_influencer_service_unverify_fails_if_influencer_in_incorrect_state(db_influencer):
    db_influencer.state = "incorrect state"

    with pytest.raises(ServiceException) as exc:
        InfluencerService(db_influencer).unverify()

    assert "Can't unverify a {} influencer".format(db_influencer.state) in exc.exconly()
    assert db_influencer.state == "incorrect state"


def test_influencer_service_unverify_success(db_influencer):
    db_influencer.state = "verified"

    with InfluencerService(db_influencer) as service:
        service.unverify()

    assert db_influencer.state == "reviewed"


def test_influencer_service_message_fails_if_sending_message_from_a_non_existing_influencer(
    db_influencer,
):
    with pytest.raises(InfluencerNotFound) as exc:
        InfluencerService(db_influencer).message("non_existing_username", "text", True)

    assert "No influencer found with the username non_existing_username" in exc.exconly()


def test_influencer_service_message_fails_if_sending_message_from_a_restricted_user(db_influencer):
    with pytest.raises(ForbiddenException) as exc:
        InfluencerService(db_influencer).message(db_influencer.username, "text", True)

    assert "Notification should be sent to a staff member's Takumi app" in exc.exconly()


def test_influencer_service_message_fails_if_sending_message_fails(
    monkeypatch, db_influencer, db_device
):
    # Arrange
    db_influencer.user.role_name = "developer"
    db_influencer.user.device = db_device

    # Act
    with mock.patch("takumi.services.influencer.NotificationClient.from_influencer") as mock_client:
        mock_client.return_value.send_instagram_direct_message.side_effect = NotificationException

        with pytest.raises(SendInfluencerMessageError) as exc:
            InfluencerService(db_influencer).message(db_influencer.username, "text", True)

    # Assert
    assert "Failed to send push notification" in exc.exconly()


def test_influencer_serivice_message_raises_if_no_device(monkeypatch, db_influencer):
    # Arrange
    db_influencer.user.role_name = "developer"

    # Act
    with mock.patch("takumi.services.influencer.NotificationClient") as mock_client:
        mock_client.return_value.has_device = False
        with pytest.raises(SendInfluencerMessageError) as exc:
            with InfluencerService(db_influencer) as service:
                service.message(db_influencer.username, "text", True)

    assert "User has no device to notify" in exc.exconly()


def test_influencer_service_message_success(monkeypatch, db_influencer, db_device):
    # Arrange
    db_influencer.user.role_name = "developer"
    db_influencer.user.device = db_device

    # Act
    with mock.patch("takumi.services.influencer.InfluencerLog.add_event") as mock_log:
        with mock.patch(
            "takumi.services.influencer.NotificationClient.from_influencer"
        ) as mock_client:
            mock_client.return_value.has_device = True
            with InfluencerService(db_influencer) as service:
                service.message(db_influencer.username, "text", True)

    # Assert
    assert mock_log.called
    assert mock_log.call_args[0] == (
        "send-instagram-direct-message",
        {"takumi_username": db_influencer.username, "text": "text", "is_dm": True},
    )


def test_get_currency_income_returns_0_when_no_offers_found(db_influencer):
    # Arrange
    db_influencer.offers = []

    # Act
    result = InfluencerService.get_market_income(db_influencer.id, us_market, 2018)

    # Assert
    assert result == 0


def test_get_currency_income_returns_remaining_usd(
    db_session, db_influencer, db_us_region, offer_factory, campaign_factory, payment_factory
):
    # Arrange
    date_2018 = dt.datetime(2018, 5, 5, tzinfo=dt.timezone.utc)
    date_2017 = dt.datetime(2017, 5, 5, tzinfo=dt.timezone.utc)

    offer_1 = offer_factory(
        campaign=campaign_factory(region=db_us_region),
        is_claimable=True,
        influencer=db_influencer,
        payable=date_2018,
        reward=1000,
    )
    offer_2 = offer_factory(
        campaign=campaign_factory(region=db_us_region),
        is_claimable=False,
        influencer=db_influencer,
        payable=date_2018,
        reward=10000,
    )
    offer_3 = offer_factory(
        campaign=campaign_factory(region=db_us_region),
        is_claimable=True,
        influencer=db_influencer,
        payable=date_2018,
        reward=100_000,
    )
    offer_4 = offer_factory(
        campaign=campaign_factory(region=db_us_region),
        is_claimable=True,
        influencer=db_influencer,
        payable=date_2018,
        reward=1_000_000,
    )
    offer_5 = offer_factory(
        campaign=campaign_factory(region=db_us_region),
        is_claimable=True,
        influencer=db_influencer,
        payable=date_2017,
        reward=10_000_000,
    )
    offer_3.payments = [payment_factory(offer=offer_3, amount=200, state=PAYMENT_STATES.FAILED)]
    offer_4.payments = [
        payment_factory(offer=offer_4, amount=33, state=PAYMENT_STATES.FAILED),
        payment_factory(offer=offer_4, amount=11, state=PAYMENT_STATES.PAID, successful=True),
    ]
    db_session.add_all([offer_1, offer_2, offer_3, offer_4, offer_5])

    # Act
    result = InfluencerService.get_market_income(db_influencer.id, db_us_region.market, 2018)

    # Assert
    assert result == 1211


def test_get_total_rewards_returns_an_empty_array_when_no_payments_have_been_claimed(db_offer):
    # Arrange
    db_offer.payments = []

    # Act
    result = InfluencerService.get_total_rewards(db_offer.influencer_id)

    # Assert
    assert result == []


def test_get_total_rewards_returns_total_rewards_per_currency(
    db_session, db_influencer, db_region, campaign_factory, offer_factory, payment_factory
):
    # Arrange
    offer_1 = offer_factory(campaign=campaign_factory(region=db_region), influencer=db_influencer)
    offer_2 = offer_factory(campaign=campaign_factory(region=db_region), influencer=db_influencer)
    offer_3 = offer_factory(campaign=campaign_factory(region=db_region), influencer=db_influencer)
    offer_4 = offer_factory(campaign=campaign_factory(region=db_region), influencer=db_influencer)
    offer_1.payments = [
        payment_factory(
            offer=offer_1,
            currency="USD",
            amount=337,
            state=PAYMENT_STATES.REQUESTED,
            successful=True,
        )
    ]
    offer_2.payments = [
        payment_factory(
            offer=offer_2,
            currency="USD",
            amount=1000,
            state=PAYMENT_STATES.REQUESTED,
            successful=True,
        )
    ]
    offer_3.payments = [
        payment_factory(
            offer=offer_3, currency="GBP", amount=1, state=PAYMENT_STATES.REQUESTED, successful=True
        )
    ]
    offer_4.payments = [
        payment_factory(
            offer=offer_4,
            currency="GBP",
            amount=1,
            state=PAYMENT_STATES.REQUESTED,
            successful=False,
        )
    ]
    db_session.add_all([offer_1, offer_2, offer_3, offer_4])

    # Act
    result = InfluencerService.get_total_rewards(db_influencer.id)

    # Assert
    assert len(result) == 2
    assert (1337, "USD") in result
    assert (1, "GBP") in result
