import mock
import pytest
from mock import call

from takumi.gql.exceptions import GraphQLException
from takumi.gql.mutation.targeting import TargetCampaign
from takumi.utils import uuid4_str


def test_target_campaign_returns_404_when_campaign_not_found(monkeypatch):
    # Arrange
    _stub_get_campaign(monkeypatch, None)

    target_campaign = _get_target_campaign_skeleton()

    # Act
    with pytest.raises(GraphQLException) as exc:
        TargetCampaign().mutate(**target_campaign)

    # Assert
    assert "Campaign ({}) not found".format(target_campaign["id"]) in exc.exconly()


def test_target_campaign_fails_when_gender_is_invalid(monkeypatch, campaign):
    # Arrange
    _stub_get_campaign(monkeypatch, campaign)

    target_campaign = _get_target_campaign_skeleton()
    target_campaign["gender"] = "non valid gender"

    # Act
    with pytest.raises(GraphQLException) as exc:
        TargetCampaign().mutate(**target_campaign)

    # Assert
    assert (
        '`Gender` must be one of "male", "female", or "all". Received "non valid gender"'
        in exc.exconly()
    )


def test_target_campaign_updates_targeting(monkeypatch, campaign):
    # Arrange
    _stub_get_campaign(monkeypatch, campaign)

    target_campaign = _get_target_campaign_skeleton()
    target_campaign["regions"] = "male"
    target_campaign["gender"] = "male"
    target_campaign["ages"] = "male"
    target_campaign["interest_ids"] = "male"

    # Act
    with mock.patch("takumi.gql.mutation.targeting.TargetingService") as mock_targeting_service:
        TargetCampaign().mutate(**target_campaign)

    # Assert
    service_calls = mock_targeting_service.return_value.__enter__.return_value
    assert call(target_campaign["regions"]) in service_calls.update_regions.mock_calls
    assert call(target_campaign["gender"]) in service_calls.update_gender.mock_calls
    assert call(target_campaign["ages"]) in service_calls.update_ages.mock_calls
    assert call(target_campaign["interest_ids"]) in service_calls.update_interests.mock_calls


#############################################
# Utility functions for tests defined below #
#############################################
@pytest.fixture(autouse=True, scope="module")
def _auto_stub_permission_decorator_required_for_mutations():
    with mock.patch("flask_principal.IdentityContext.can", return_value=True):
        yield


def _stub_get_advertiser(monkeypatch, value):
    monkeypatch.setattr(
        "takumi.gql.utils.AdvertiserService.get_by_id", mock.Mock(return_value=value)
    )


def _stub_get_campaign(monkeypatch, value):
    monkeypatch.setattr("takumi.gql.utils.CampaignService.get_by_id", mock.Mock(return_value=value))


def _get_target_campaign_skeleton():
    return {
        "info": "info",
        "id": uuid4_str(),
        "regions": None,
        "gender": None,
        "ages": None,
        "interest_ids": None,
    }
