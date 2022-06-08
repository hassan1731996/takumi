import datetime as dt

from takumi.models import Influencer, User
from takumi.models.influencer import is_timestamp_newer
from takumi.schemas.influencer_info import InfluencerInfoSchema


def _get_test_user(created=None, terms_accepted=None, privacy_accepted=None):

    if created is None:
        created = dt.datetime.now(dt.timezone.utc)

    if terms_accepted is None:
        terms_accepted = dt.datetime.now(dt.timezone.utc)

    if privacy_accepted is None:
        privacy_accepted = dt.datetime.now(dt.timezone.utc)

    user = User(created=created, settings={}, role_name="influencer")
    influencer = Influencer(
        info=dict(
            terms_accepted=terms_accepted.isoformat(), privacy_accepted=privacy_accepted.isoformat()
        )
    )
    user.influencer = influencer
    return user


def test_influencer_info_older_accepted_terms_results_in_false(monkeypatch):
    monkeypatch.setattr(
        "takumi.models.influencer.LATEST_TERMS_TIMESTAMP",
        dt.datetime(2016, 1, 1, tzinfo=dt.timezone.utc),
    )

    user = _get_test_user(terms_accepted=dt.datetime(2001, 1, 1))
    serialized = InfluencerInfoSchema(context={"user": user}).dump(user.settings).data
    assert serialized["has_accepted_latest_terms"] is False


def test_influencer_info_newer_accepted_terms_results_in_true(monkeypatch):
    monkeypatch.setattr(
        "takumi.models.influencer.LATEST_TERMS_TIMESTAMP",
        dt.datetime(2016, 1, 1, tzinfo=dt.timezone.utc),
    )

    user = _get_test_user(terms_accepted=dt.datetime(2016, 1, 2, tzinfo=dt.timezone.utc))
    serialized = InfluencerInfoSchema(context={"user": user}).dump(user.settings).data
    assert serialized["has_accepted_latest_terms"] is True


def test_influencer_info_no_accepted_terms_value_results_false(monkeypatch):
    term_change_date = dt.datetime(2016, 1, 1, tzinfo=dt.timezone.utc)
    monkeypatch.setattr("takumi.models.influencer.LATEST_TERMS_TIMESTAMP", term_change_date)

    user = _get_test_user()
    del user.influencer.info["terms_accepted"]

    serialized = InfluencerInfoSchema(context={"user": user}).dump(user.settings).data
    assert serialized["has_accepted_latest_terms"] is False


def test_influencer_info_older_accepted_privacy_results_in_false(monkeypatch):
    monkeypatch.setattr(
        "takumi.models.influencer.LATEST_PRIVACY_TIMESTAMP",
        dt.datetime(2016, 1, 1, tzinfo=dt.timezone.utc),
    )

    user = _get_test_user(privacy_accepted=dt.datetime(2001, 1, 1, tzinfo=dt.timezone.utc))
    serialized = InfluencerInfoSchema(context={"user": user}).dump(user.settings).data
    assert serialized["has_accepted_latest_privacy"] is False


def test_influencer_info_newer_accepted_privacy_results_in_true(monkeypatch):
    monkeypatch.setattr(
        "takumi.models.influencer.LATEST_PRIVACY_TIMESTAMP",
        dt.datetime(2016, 1, 1, tzinfo=dt.timezone.utc),
    )

    user = _get_test_user(privacy_accepted=dt.datetime(2016, 1, 2, tzinfo=dt.timezone.utc))
    serialized = InfluencerInfoSchema(context={"user": user}).dump(user.settings).data
    assert serialized["has_accepted_latest_privacy"] is True


def test_influencer_info_no_accepted_privacy_value_results_in_false(monkeypatch):
    privacy_change_date = dt.datetime(2016, 1, 1, tzinfo=dt.timezone.utc)
    monkeypatch.setattr("takumi.models.influencer.LATEST_PRIVACY_TIMESTAMP", privacy_change_date)

    user = _get_test_user()
    del user.influencer.info["privacy_accepted"]

    serialized = InfluencerInfoSchema(context={"user": user}).dump(user.settings).data
    assert serialized["has_accepted_latest_privacy"] is False


def test_is_timestamp_newer_key_missing_uses_default():
    stale = dt.datetime(2001, 1, 1, tzinfo=dt.timezone.utc)
    fresh = dt.datetime(2002, 1, 1, tzinfo=dt.timezone.utc)
    assert is_timestamp_newer(dict(), "mockey", value=stale, default=fresh) == True
    assert is_timestamp_newer(dict(), "mockey", value=fresh, default=stale) == False


def test_is_timestamp_newer_key_missing_is_false():
    stale = dt.datetime(2001, 1, 1, tzinfo=dt.timezone.utc)
    fresh = dt.datetime(2002, 1, 1, tzinfo=dt.timezone.utc)
    assert is_timestamp_newer(dict(), "mockey", value=stale) == False
    assert is_timestamp_newer(dict(mockey=fresh.isoformat()), "mockey", value=stale) == True


def test_is_timestamp_newer_is_false_for_equal():
    fresh = dt.datetime(2002, 1, 1, tzinfo=dt.timezone.utc)
    assert is_timestamp_newer(dict(mockey=fresh.isoformat()), "mockey", value=fresh) == False
