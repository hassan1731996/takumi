# encoding=utf-8
import datetime as dt

from freezegun import freeze_time

from takumi.constants import EMAIL_VERIFICATION_MAX_AGE_SECONDS
from takumi.models import EmailLogin
from takumi.schemas import EmailLoginSchema


@freeze_time(dt.datetime.now(dt.timezone.utc))
def test_email_login_schema(monkeypatch):
    # Arrange
    email_login = EmailLogin(
        email="test_email@takumi.com", verified=False, created=dt.datetime.now(dt.timezone.utc)
    )

    # Act
    data = EmailLoginSchema().dump(email_login).data

    # Assert
    assert data["time_to_live"] == EMAIL_VERIFICATION_MAX_AGE_SECONDS  # 7 days
