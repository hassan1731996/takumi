import datetime as dt

from tasktiger.schedule import periodic

from takumi.constants import EMAIL_VERIFICATION_MAX_AGE_DAYS
from takumi.extensions import tiger
from takumi.models import EmailLogin
from takumi.services import UserService


@tiger.scheduled(periodic(hours=24, start_date=dt.datetime(2000, 1, 1, 5, 30)))  # Run 5:30 GMT
def cleanup_emails() -> None:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=EMAIL_VERIFICATION_MAX_AGE_DAYS)

    # Get non verified EmailLogin, older than EMAIL_VERIFICATION_MAX_AGE_DAYS
    q = EmailLogin.query.filter(~EmailLogin.verified, EmailLogin.created < cutoff)

    for email_login in q:
        UserService.delete_user(email_login.user)
