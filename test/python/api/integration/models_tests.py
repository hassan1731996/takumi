# encoding=utf-8
import os

from takumi.models import EmailLogin, User

running_in_ci = os.environ.get("CIRCLECI") is not None


def test_email_login_get(db_session, db_developer_user):
    db_developer_user.email_login.email = "j@example.com"

    assert EmailLogin.get("J@example.com").email == "j@example.com"


def test_email_login_password(db_session):
    obj = EmailLogin()
    obj.set_password("a")
    assert obj.check_password("a")
    assert not obj.check_password("b")


def test_delete_user_also_deletes_email(db_session, db_advertiser_user, email_login_factory):
    db_advertiser_user.email_login.email = "a@example.com"
    db_session.commit()

    db_session.connection().execute(
        "DELETE FROM public.user WHERE id = '{}'::uuid".format(db_advertiser_user.id)
    )
    db_session.commit()

    obj = EmailLogin.get("a@example.com")
    assert obj is None


def test_delete_email_does_not_delete_user(db_session, db_advertiser_user, email_login_factory):
    db_session.delete(db_advertiser_user.email_login)
    db_session.commit()

    obj = User.query.get(db_advertiser_user.id)
    assert obj is not None


def test_target_and_supported_ancestor(db_region_city):
    assert db_region_city.target is db_region_city

    db_region_city.supported = False

    assert db_region_city.target is db_region_city.parent

    db_region_city.parent.supported = False

    assert db_region_city.target is db_region_city.parent.parent

    db_region_city.parent.parent.supported = False

    assert db_region_city.target is db_region_city
