# encoding=utf-8

import datetime as dt

import mock
import pytest
from flask import url_for

from takumi.extensions import db
from takumi.schemas import SelfInfluencerSchema
from takumi.services.influencer import ServiceException, limited_targeting_update


@pytest.mark.usefixtures("disable_influencer_total_rewards")
def test_users_self_influencer_object_contains_provider_data(influencer):
    serialized_data = (
        SelfInfluencerSchema(context={"user": influencer.user}).dump(influencer.user).data
    )
    assert serialized_data["influencer"]["instagram_account"]["followers"] == 1000
    assert serialized_data["influencer"]["username"] == influencer.username


@pytest.mark.usefixtures("disable_influencer_total_rewards")
def test_users_self_gender(influencer_client, influencer, monkeypatch):
    monkeypatch.setattr(db.session, "commit", lambda: None)

    with mock.patch("sqlalchemy.orm.query.Query.scalar") as m:
        m.return_value = None
        response = influencer_client.put(
            url_for("api.influencer_settings"), data={"gender": "female"}
        )
    assert response.status_code == 200
    assert response.json["gender"] == "female"
    assert influencer.user.gender == "female"


@pytest.mark.usefixtures("disable_influencer_total_rewards")
def test_users_self_gender_none_is_supported(influencer_client, influencer, monkeypatch):
    monkeypatch.setattr(db.session, "commit", lambda: None)

    with mock.patch("sqlalchemy.orm.query.Query.scalar") as m:
        m.return_value = None
        response = influencer_client.put(url_for("api.influencer_settings"), data={"gender": None})
    assert response.status_code == 200
    assert response.json["gender"] is None
    assert influencer.user.gender is None


def test_users_self_gender_not_supported(influencer_client, influencer, monkeypatch):
    monkeypatch.setattr(db.session, "commit", lambda: None)

    with mock.patch("sqlalchemy.orm.query.Query.scalar") as m:
        m.return_value = None
        response = influencer_client.put(
            url_for("api.influencer_settings"), data={"gender": "trans"}
        )
    assert response.status_code == 422


@pytest.mark.usefixtures("disable_influencer_total_rewards")
def test_settings_response(influencer_client, influencer, monkeypatch):
    monkeypatch.setattr(db.session, "commit", lambda: None)
    response = influencer_client.put(url_for("api.influencer_settings"), data={})
    assert response.status_code == 200


@pytest.mark.usefixtures("disable_influencer_total_rewards")
def test_settings_full_name(influencer_client, influencer, monkeypatch):
    monkeypatch.setattr(db.session, "commit", lambda: None)
    response = influencer_client.put(
        url_for("api.influencer_settings"), data={"full_name": "Heisenberg"}
    )
    assert response.json["full_name"] == "Heisenberg"
    assert influencer.user.full_name == "Heisenberg"


def test_settings_birthday_too_young(influencer_client, influencer, monkeypatch):
    monkeypatch.setattr(db.session, "commit", lambda: None)
    with mock.patch("sqlalchemy.orm.query.Query.scalar"):
        response = influencer_client.put(
            url_for("api.influencer_settings"),
            data={"birthday": dt.datetime.now(dt.timezone.utc).isoformat()},
        )
    assert response.status_code == 422


@pytest.mark.usefixtures("disable_influencer_total_rewards")
def test_settings_birthday_validation(influencer_client, influencer, monkeypatch):
    monkeypatch.setattr(db.session, "commit", lambda: None)
    with mock.patch("sqlalchemy.orm.query.Query.scalar") as m:
        m.return_value = None
        response = influencer_client.put(
            url_for("api.influencer_settings"), data={"birthday": "1995-06-17"}
        )
    assert response.status_code == 200
    assert response.json["birthday"] == "1995-06-17"
    assert influencer.user.birthday == dt.date(1995, 6, 17)


@pytest.mark.usefixtures("disable_influencer_total_rewards")
def test_settings_full_name_empty_string(influencer_client, influencer):
    for bad_value in [None, 1]:
        response = influencer_client.put(
            url_for("api.influencer_settings"), data={"full_name": bad_value}
        )
        assert response.status_code == 422


def test_limited_targeting_update(influencer_user):
    with mock.patch("sqlalchemy.orm.query.Query.scalar") as m:
        m.return_value = None
        with limited_targeting_update(influencer_user, "birthday"):
            pass


def test_limited_targeting_update_raises_error(influencer_user):
    with mock.patch("sqlalchemy.orm.query.Query.scalar") as m:
        m.return_value = dt.datetime.now(dt.timezone.utc)
        with pytest.raises(ServiceException):
            with limited_targeting_update(influencer_user, "birthday"):
                pass


def test_user_targeting_update_passes(influencer_user):
    with mock.patch("sqlalchemy.orm.query.Query.scalar") as m:
        m.return_value = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=31)
        with limited_targeting_update(influencer_user, "birthday"):
            pass


def test_user_influencer_address(influencer_client, address, influencer):
    resp = influencer_client.get(url_for("api.get_address"))
    assert resp.status_code == 200
    assert resp.json["address1"] == address.address1


def test_user_influencer_address_missing_has_defaults(influencer_client, influencer):
    resp = influencer_client.get(url_for("api.get_address"))
    assert resp.status_code == 200
    assert resp.json["address1"] == ""
    assert resp.json["country"] == influencer.target_region.country_code


def test_user_influencer_set_address(influencer_client, influencer, monkeypatch):
    monkeypatch.setattr(db.session, "commit", lambda: None)
    resp = influencer_client.put(
        url_for("api.set_address"),
        data={
            "address1": "Mock Home 1",
            "address2": "",
            "is_pobox": False,
            "city": "Mockatown",
            "postal_code": "SW1H 9BP",
            "state": None,
            "phonenumber": "123",
        },
    )
    assert resp.status_code == 200
    assert resp.json["address1"] == "Mock Home 1"
    assert influencer.address.address1 == "Mock Home 1"


def test_user_influencer_delete_address_deletes_returns_defaults(
    influencer_client, influencer, address, monkeypatch
):
    monkeypatch.setattr(db.session, "commit", lambda: None)
    with mock.patch("sqlalchemy.orm.session.Session.delete") as mock_delete:
        resp = influencer_client.delete(url_for("api.delete_address"))
    assert resp.status_code == 200
    assert mock_delete.called
    assert mock_delete.call_args[0][0] == address
    assert resp.json["country"] == influencer.target_region.country_code


def test_user_address_missing_with_post_without_shipping_required(offer, post):
    post.campaign.shipping_required = False
    assert offer.address_missing is False

    post.campaign.shipping_required = True
    assert offer.address_missing is True
