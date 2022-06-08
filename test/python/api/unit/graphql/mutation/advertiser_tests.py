# encoding=utf-8

import mock
import pytest

from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.advertiser import CreateAdvertiser, RemoveUserFromAdvertiser
from takumi.services import AdvertiserService
from takumi.utils import uuid4_str


def test_create_advertiser_fails_for_invalid_brand_domain(monkeypatch):
    # Arrange
    new_brand = _get_create_advertiser_skeleton()
    new_brand["unique_ref"] = "æ"

    # Act
    with pytest.raises(MutationException) as exc:
        CreateAdvertiser().mutate(**new_brand)

    # Assert
    assert 'Brand "domain" (`unique reference`) can not contain special characters' in exc.exconly()


def test_create_advertiser_fails_for_already_existing_brand_domain(
    monkeypatch, advertiser_user, client
):
    # Arrange
    _stub_validation_for_pre_existing_advertiser_domain(monkeypatch, True)

    # Act
    with client.user_request_context(advertiser_user):
        with pytest.raises(MutationException) as exc:
            CreateAdvertiser().mutate(**_get_create_advertiser_skeleton())

    # Assert
    assert "Advertiser with this `unique reference` exists" in exc.exconly()


def test_create_advertiser_creates_advertiser(monkeypatch, developer_user, advertiser, region):
    # Arrange
    _stub_validation_for_pre_existing_advertiser_domain(monkeypatch, False)

    monkeypatch.setattr("takumi.gql.mutation.advertiser.get_region_or_404", lambda x: region)
    monkeypatch.setattr("takumi.gql.mutation.advertiser.current_user", developer_user)
    monkeypatch.setattr(
        "takumi.gql.mutation.advertiser.upload_media_to_cdn",
        lambda *args: "https://imgix.com/image.jpg",
    )

    # Act
    with mock.patch(
        "takumi.gql.mutation.advertiser.AdvertiserService.create_advertiser",
        return_value=advertiser,
    ) as mock_create_advertiser:
        response = CreateAdvertiser().mutate(**_get_create_advertiser_skeleton())

    # Assert
    mock_create_advertiser.assert_called_once_with(
        developer_user, "uniqueref", "https://imgix.com/image.jpg", "name", region, None, None, None
    )
    assert response.advertiser == advertiser


def test_create_advertiser_with_industries(monkeypatch, developer_user, advertiser, region, client):
    _stub_validation_for_pre_existing_advertiser_domain(monkeypatch, False)

    monkeypatch.setattr("takumi.gql.mutation.advertiser.get_region_or_404", lambda x: region)
    monkeypatch.setattr(
        "takumi.gql.mutation.advertiser.upload_media_to_cdn",
        lambda *args: "https://imgix.com/image.jpg",
    )

    with client.user_request_context(developer_user):
        with mock.patch(
            "takumi.gql.mutation.advertiser.AdvertiserService.create_advertiser",
            return_value=advertiser,
        ) as mock_create_advertiser:
            advertiser_skeleton = _get_create_advertiser_skeleton()
            advertiser_skeleton["advertiser_industries_ids"] = [uuid4_str(), uuid4_str()]

            response = CreateAdvertiser().mutate(**advertiser_skeleton)

    mock_create_advertiser.assert_called_once_with(
        developer_user,
        "uniqueref",
        "https://imgix.com/image.jpg",
        "name",
        region,
        None,
        None,
        advertiser_skeleton["advertiser_industries_ids"],
    )
    assert response.advertiser == advertiser


def test_remove_user_from_advertiser_calls_service(advertiser, advertiser_user, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr(
        "takumi.gql.mutation.advertiser.get_advertiser_or_404", lambda _: advertiser
    )
    monkeypatch.setattr("takumi.gql.mutation.advertiser.get_user_or_404", lambda _: advertiser_user)

    with mock.patch.object(AdvertiserService, "remove_user") as mock_remove_user:
        RemoveUserFromAdvertiser().mutate("info", id=advertiser.id, user_id=advertiser_user.id)

    mock_remove_user.assert_called_with(advertiser_user)


#############################################
# Utility functions for tests defined below #
#############################################
@pytest.fixture(autouse=True, scope="module")
def _auto_stub_permission_decorator_required_for_mutations():
    with mock.patch("flask_principal.IdentityContext.can", return_value=True):
        yield


def _stub_validation_for_pre_existing_advertiser_domain(monkeypatch, value):
    monkeypatch.setattr(
        "takumi.gql.mutation.advertiser.AdvertiserService.advertiser_with_domain_exists",
        mock.Mock(return_value=value),
    )


def _get_create_advertiser_skeleton():
    return {
        "info": "info",
        "name": "name",
        "profile_picture": "uk",
        "region_id": uuid4_str(),
        "unique_ref": "uniqueref",
        "instagram_user": None,
        "vat_number": None,
    }
