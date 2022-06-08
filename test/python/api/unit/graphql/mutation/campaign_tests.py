import mock
import pytest
from mock import call

from takumi.gql.exceptions import GraphQLException, MutationException
from takumi.gql.mutation.campaign import (
    CreateCampaign,
    NotifyAllTargetsInCampaign,
    RestoreCampaign,
    RevokeRequestedOffers,
    StashCampaign,
    UpdateCampaign,
)
from takumi.models.campaign import STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.post import PostTypes
from takumi.services import CampaignService
from takumi.utils import uuid4_str


################################
# Tests for creating campaigns #
################################
def test_create_campaign_fails_for_wrong_industry():
    # Arrange
    new_campaign = _get_create_campaign_skeleton()
    new_campaign["industry"] = "illegal industry"

    # Act
    with pytest.raises(MutationException) as exc:
        CreateCampaign().mutate(**new_campaign)

    # Assert
    assert '"illegal industry" is not a valid `industry` value' in exc.exconly()


def test_create_campaign_with_invalid_campaign_manager_returns_404(monkeypatch):
    # Arrange
    _stub_get_user(monkeypatch, None)

    new_campaign = _get_create_campaign_skeleton()
    new_campaign["campaign_manager"] = uuid4_str()

    # Act
    with pytest.raises(GraphQLException) as exc:
        CreateCampaign().mutate(**new_campaign)

    # Assert
    assert "User ({}) not found".format(new_campaign["campaign_manager"]) in exc.exconly()


def test_create_campaign_with_invalid_secondary_campaign_manager_returns_404(monkeypatch):
    # Arrange
    _stub_get_user(monkeypatch, None)

    new_campaign = _get_create_campaign_skeleton()
    new_campaign["secondary_campaign_manager"] = uuid4_str()

    # Act
    with pytest.raises(GraphQLException) as exc:
        CreateCampaign().mutate(**new_campaign)

    # Assert
    assert "User ({}) not found".format(new_campaign["secondary_campaign_manager"]) in exc.exconly()


def test_create_campaign_with_invalid_community_manager_returns_404(monkeypatch):
    # Arrange
    _stub_get_user(monkeypatch, None)

    new_campaign = _get_create_campaign_skeleton()
    new_campaign["community_manager"] = uuid4_str()

    # Act
    with pytest.raises(GraphQLException) as exc:
        CreateCampaign().mutate(**new_campaign)

    # Assert
    assert "User ({}) not found".format(new_campaign["community_manager"]) in exc.exconly()


def test_create_campaign_with_invalid_advertiser_id_returns_404(monkeypatch):
    # Arrange
    _stub_get_advertiser(monkeypatch, None)

    new_campaign = _get_create_campaign_skeleton()

    # Act
    with pytest.raises(GraphQLException) as exc:
        CreateCampaign().mutate(**new_campaign)

    # Assert
    assert "Advertiser ({}) not found".format(new_campaign["advertiser_id"]) in exc.exconly()


def test_create_campaign_with_invalid_owner_returns_404(monkeypatch, advertiser):
    # Arrange
    _stub_get_advertiser(monkeypatch, advertiser)
    _stub_get_user(monkeypatch, None)

    new_campaign = _get_create_campaign_skeleton()
    new_campaign["owner"] = uuid4_str()

    # Act
    with pytest.raises(GraphQLException) as exc:
        CreateCampaign().mutate(**new_campaign)

    # Assert
    assert "User ({}) not found".format(new_campaign["owner"]) in exc.exconly()


def test_create_campaign_with_invalid_market_returns_404(monkeypatch, developer_user, advertiser):
    # Arrange
    _stub_get_advertiser(monkeypatch, advertiser)
    _stub_current_user(monkeypatch, developer_user)

    new_campaign = _get_create_campaign_skeleton()
    new_campaign["market_slug"] = None

    # Act
    with pytest.raises(GraphQLException) as exc:
        CreateCampaign().mutate(**new_campaign)

    # Assert
    assert "Market ({}) not found".format(new_campaign["market_slug"]) in exc.exconly()


def test_create_campaign_creates_a_campaign(
    monkeypatch, developer_user, advertiser, market, campaign
):
    # Arrange
    _stub_get_advertiser(monkeypatch, advertiser)
    _stub_current_user(monkeypatch, developer_user)
    _stub_create_targeting(monkeypatch)
    _stub_create_post(monkeypatch)
    _stub_create_campaign(monkeypatch)
    monkeypatch.setattr("takumi.gql.mutation.campaign.TargetingService", mock.MagicMock())

    new_campaign = _get_create_campaign_skeleton()

    # Act
    with mock.patch(
        "takumi.gql.mutation.campaign.CampaignService.create_campaign", return_value=campaign
    ) as mock_campaign:
        with mock.patch("takumi.gql.mutation.campaign.PostService.create_post") as mock_create_post:
            CreateCampaign().mutate(**new_campaign)

    # Assert
    expected_call_args = dict(
        advertiser_id=advertiser.id,
        market=market,
        reward_model=new_campaign["reward_model"],
        units=new_campaign["units"],
        shipping_required=new_campaign["shipping_required"],
        require_insights=new_campaign["require_insights"],
        price=new_campaign["price"],
        list_price=new_campaign["list_price"],
        custom_reward_units=None,
        name=None,
        description=None,
        pictures=new_campaign["pictures"],
        prompts=[],
        owner_id=developer_user.id,
        campaign_manager_id=None,
        secondary_campaign_manager_id=None,
        community_manager_id=None,
        tags=None,
        has_nda=False,
        brand_safety=False,
        extended_review=False,
        industry=None,
        opportunity_product_id=None,
        brand_match=False,
        pro_bono=False,
    )
    assert mock_campaign.call_args[1] == expected_call_args
    mock_create_post.assert_called_once_with(campaign.id, PostTypes.standard)


################################
# Tests for updating campaigns #
################################
def test_update_campaign_returns_404_when_campaign_not_found(monkeypatch):
    # Arrange
    _stub_get_campaign(monkeypatch, None)

    update_campaign = _get_update_campaign_skeleton()

    # Act
    with pytest.raises(GraphQLException) as exc:
        UpdateCampaign().mutate(**update_campaign)

    # Assert
    assert "Campaign ({}) not found".format(update_campaign["id"]) in exc.exconly()


def test_update_campaign_with_invalid_owner_returns_404(monkeypatch, campaign):
    # Arrange
    _stub_get_campaign(monkeypatch, campaign)
    _stub_get_user(monkeypatch, None)

    update_campaign = _get_update_campaign_skeleton()
    update_campaign["owner"] = uuid4_str()

    with pytest.raises(GraphQLException) as exc:
        UpdateCampaign().mutate(**update_campaign)

    # Assert
    assert "User ({}) not found".format(update_campaign["owner"]) in exc.exconly()


def test_update_campaign_with_invalid_campaign_manager_returns_404(monkeypatch, campaign):
    # Arrange
    _stub_get_campaign(monkeypatch, campaign)
    _stub_get_user(monkeypatch, None)

    update_campaign = _get_update_campaign_skeleton()
    update_campaign["campaign_manager"] = uuid4_str()

    with pytest.raises(GraphQLException) as exc:
        UpdateCampaign().mutate(**update_campaign)

    # Assert
    assert "User ({}) not found".format(update_campaign["campaign_manager"]) in exc.exconly()


def test_update_campaign_with_invalid_secondary_campaign_manager_returns_404(monkeypatch, campaign):
    # Arrange
    _stub_get_campaign(monkeypatch, campaign)
    _stub_get_user(monkeypatch, None)

    update_campaign = _get_update_campaign_skeleton()
    update_campaign["secondary_campaign_manager"] = uuid4_str()

    with pytest.raises(GraphQLException) as exc:
        UpdateCampaign().mutate(**update_campaign)

    # Assert
    assert (
        "User ({}) not found".format(update_campaign["secondary_campaign_manager"]) in exc.exconly()
    )


def test_update_campaign_with_invalid_community_manager_returns_404(monkeypatch, campaign):
    # Arrange
    _stub_get_campaign(monkeypatch, campaign)
    _stub_get_user(monkeypatch, None)

    update_campaign = _get_update_campaign_skeleton()
    update_campaign["community_manager"] = uuid4_str()

    with pytest.raises(GraphQLException) as exc:
        UpdateCampaign().mutate(**update_campaign)

    # Assert
    assert "User ({}) not found".format(update_campaign["community_manager"]) in exc.exconly()


def test_update_campaign_validates_view_model(monkeypatch, campaign):
    # Arrange
    monkeypatch.setattr(
        "takumi.gql.utils.UserService.get_by_id",
        mock.Mock(
            side_effect=[
                "owner",
                "campaign_manager",
                "secondary_campaign_manager",
                "community_manager",
            ]
        ),
    )  # mock 3 calls

    owner = uuid4_str()
    campaign_manager = uuid4_str()
    secondary_campaign_manager = uuid4_str()
    community_manager = uuid4_str()

    # Act & Assert
    UpdateCampaign()._validate_view_model(
        campaign, owner, campaign_manager, secondary_campaign_manager, community_manager
    )


def test_update_campaign_updates_campaign(monkeypatch, campaign, post):
    # Arrange
    campaign.posts = [post, post]
    campaign.custom_reward_units = 1337
    _stub_get_campaign(monkeypatch, campaign)
    monkeypatch.setattr(
        "takumi.gql.utils.UserService.get_by_id",
        mock.Mock(
            side_effect=[
                "owner",
                "campaign_manager",
                "secondary_campaign_manager",
                "community_manager",
            ]
        ),
    )  # mock 3 calls
    monkeypatch.setattr("takumi.gql.mutation.user.permissions.developer.can", lambda: True)

    update_campaign = _get_update_campaign_skeleton()
    update_campaign["owner"] = uuid4_str()
    update_campaign["campaign_manager"] = uuid4_str()
    update_campaign["secondary_campaign_manager"] = uuid4_str()
    update_campaign["community_manager"] = uuid4_str()
    update_campaign["list_price"] = 1337
    update_campaign["tags"] = ["one", "two"]
    update_campaign["custom_reward_units"] = -1

    # Act
    with mock.patch("takumi.gql.mutation.campaign.CampaignService") as mock_campaign_service:
        UpdateCampaign().mutate(**update_campaign)

    # Assert
    service_calls = mock_campaign_service.return_value.__enter__.return_value
    assert call(update_campaign["owner"]) in service_calls.update_owner.mock_calls
    assert (
        call(update_campaign["campaign_manager"])
        in service_calls.update_campaign_manager.mock_calls
    )
    assert (
        call(update_campaign["secondary_campaign_manager"])
        in service_calls.update_secondary_campaign_manager.mock_calls
    )
    assert (
        call(update_campaign["community_manager"])
        in service_calls.update_community_manager.mock_calls
    )
    assert call(update_campaign["list_price"] * 100) in service_calls.update_list_price.mock_calls
    assert call(update_campaign["tags"]) in service_calls.update_tags.mock_calls
    assert call(None) in service_calls.update_custom_reward_units.mock_calls


def test_stash_campaign_updates_campaign(app, campaign, monkeypatch):
    _stub_get_campaign(monkeypatch, campaign)
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)

    with mock.patch.object(CampaignService, "stash") as stash_mock:
        StashCampaign().mutate("info", campaign.id)
        stash_mock.assert_called_once_with()


def test_restore_campaign_updates_campaign(app, campaign, monkeypatch):
    _stub_get_campaign(monkeypatch, campaign)
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)

    campaign.state = STATES.STASHED

    with mock.patch.object(CampaignService, "restore") as stash_mock:
        RestoreCampaign().mutate("info", campaign.id)
        stash_mock.assert_called_once_with()


def test_updating_price_updates_campaign(app, campaign, monkeypatch):
    _stub_get_campaign(monkeypatch, campaign)
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)

    with mock.patch.object(CampaignService, "update_price") as mock_update:
        UpdateCampaign().mutate("info", campaign.id, price=12345)

    mock_update.assert_called_once_with(1_234_500)


def test_notify_all_targets_in_campaign_calls_service_function(app, campaign, monkeypatch):
    _stub_get_campaign(monkeypatch, campaign)
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)

    with mock.patch.object(CampaignService, "send_notifications_to_all_targets") as mock_update:
        NotifyAllTargetsInCampaign().mutate("info", campaign.id, 24)

    mock_update.assert_called_once_with(24)


def test_revoke_requested_offers_calls_service_function_when_there_are_requested_offers(
    app, campaign, monkeypatch, offer
):
    offer.state = OFFER_STATES.REQUESTED
    _stub_get_campaign(monkeypatch, campaign)
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)

    with mock.patch.object(CampaignService, "revoke_requested_offers") as mock_update:
        RevokeRequestedOffers().mutate("info", campaign.id, OFFER_STATES.REQUESTED)

    mock_update.assert_called_once()


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


def _stub_current_user(monkeypatch, value):
    monkeypatch.setattr("takumi.gql.mutation.campaign.current_user", value)


def _stub_get_user(monkeypatch, value):
    monkeypatch.setattr("takumi.gql.utils.UserService.get_by_id", mock.Mock(return_value=value))


def _stub_create_targeting(monkeypatch):
    monkeypatch.setattr(
        "takumi.gql.mutation.campaign.TargetingService.create_targeting",
        mock.Mock(return_value=None),
    )


def _stub_create_post(monkeypatch):
    monkeypatch.setattr(
        "takumi.gql.mutation.campaign.PostService.create_post", mock.Mock(return_value=None)
    )


def _stub_create_campaign(monkeypatch):
    monkeypatch.setattr(
        "takumi.gql.mutation.campaign.CampaignService.create_campaign", mock.Mock(return_value=None)
    )


def _stub_get_campaign(monkeypatch, value):
    monkeypatch.setattr("takumi.gql.utils.CampaignService.get_by_id", mock.Mock(return_value=value))


def _get_create_campaign_skeleton():
    return {
        "info": "info",
        "advertiser_id": uuid4_str(),
        "market_slug": "uk",
        "reward_model": "assets",
        "units": 0,
        "price": 0,
        "list_price": 0,
        "shipping_required": False,
        "require_insights": False,
        "pictures": [],
        "prompts": [],
        "has_nda": False,
        "brand_safety": False,
        "extended_review": False,
        "brand_match": False,
        "pro_bono": False,
    }


def _get_update_campaign_skeleton():
    return {
        "info": "info",
        "id": uuid4_str(),
        "units": None,
        "shipping_required": None,
        "require_insights": None,
        "name": None,
        "description": None,
        "pictures": None,
        "owner": None,
        "campaign_manager": None,
        "secondary_campaign_manager": None,
        "community_manager": None,
        "has_nda": None,
        "brand_safety": None,
        "extended_review": None,
        "industry": None,
        "push_notification_message": None,
    }
