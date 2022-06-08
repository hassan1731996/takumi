import datetime as dt
from functools import partial

from freezegun import freeze_time

from takumi.notifications import NotificationClient

NOW = dt.datetime(2018, 1, 10, tzinfo=dt.timezone.utc)


@freeze_time(NOW)
def test_notification_client_uses_latest_valid_device(db_session, db_influencer, device_factory):
    factory = partial(device_factory)

    factory(
        active=False, last_used=NOW - dt.timedelta(days=5, hours=2), device_model="Inactive Old"
    )
    factory(active=False, last_used=NOW - dt.timedelta(hours=2), device_model="Inactive new")
    factory(active=True, last_used=NOW - dt.timedelta(days=5, hours=1), device_model="Active old")
    factory(active=True, last_used=None, device_model="Active, but no last_used")

    valid_device = factory(
        active=True, last_used=NOW - dt.timedelta(hours=1), device_model="Active, new (correct)"
    )

    db_influencer.user.device = valid_device
    db_session.commit()
    client = NotificationClient.from_influencer(db_influencer)
    assert client.devices == [valid_device]
