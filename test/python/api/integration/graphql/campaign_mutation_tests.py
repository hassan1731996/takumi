import pytest

from takumi.gql.mutation.campaign import CreateCampaign, SetReportSummary
from takumi.models.campaign import RewardModels
from takumi.services.exceptions import InvalidPromptsException


def _get_create_campaign_skeleton(advertiser):
    return {
        "advertiser_id": advertiser.id,
        "market_slug": "uk",
        "units": 100,
        "shipping_required": False,
        "require_insights": False,
        "price": 10000,
        "list_price": 10000,
        "pictures": [],
        "prompts": [],
        "has_nda": False,
        "brand_safety": False,
        "extended_review": False,
        "brand_match": False,
        "pro_bono": False,
    }


def test_create_campaign_mutation_defaults_max_followers_targeting_if_asset(
    client, db_advertiser, db_developer_user
):
    campaign_args = _get_create_campaign_skeleton(db_advertiser)
    with client.user_request_context(db_developer_user):
        response = CreateCampaign().mutate(
            "info", reward_model=RewardModels.assets, **campaign_args
        )

    assert response.campaign.targeting.max_followers == 40000

    with client.user_request_context(db_developer_user):
        response = CreateCampaign().mutate("info", reward_model=RewardModels.reach, **campaign_args)

    assert response.campaign.targeting.max_followers == None


def test_create_campaign_fails_for_invalid_prompts_when_prompts_missing_choices_for_multiple_choice(
    client, db_developer_user, db_advertiser
):
    # Arrange
    new_campaign = _get_create_campaign_skeleton(db_advertiser)
    new_campaign["prompts"] = [dict(type="multiple_choice", choices=[""], text="123")]

    # Act
    with client.user_request_context(db_developer_user):
        with pytest.raises(InvalidPromptsException) as exc:
            CreateCampaign().mutate("info", reward_model=RewardModels.assets, **new_campaign)

    # Assert
    assert "Prompt must have at least" in exc.exconly()


def test_create_campaign_fails_for_invalid_prompts_when_prompts_missing_choices_for_single_choice(
    client, db_developer_user, db_advertiser
):
    # Arrange
    new_campaign = _get_create_campaign_skeleton(db_advertiser)
    new_campaign["prompts"] = [dict(type="single_choice", choices=[""], text="123")]

    # Act
    with client.user_request_context(db_developer_user):
        with pytest.raises(InvalidPromptsException) as exc:
            CreateCampaign().mutate("info", reward_model=RewardModels.assets, **new_campaign)

    # Assert
    assert "Prompt must have at least" in exc.exconly()


def test_create_campaign_fails_for_invalid_prompts_when_prompts_missing_choices_for_confirmation(
    client, db_developer_user, db_advertiser
):
    # Arrange
    new_campaign = _get_create_campaign_skeleton(db_advertiser)
    new_campaign["prompts"] = [dict(type="confirm", choices=[""])]

    # Act
    with client.user_request_context(db_developer_user):
        with pytest.raises(InvalidPromptsException) as exc:
            CreateCampaign().mutate("info", reward_model=RewardModels.assets, **new_campaign)

    # Assert
    assert "must have at least" in exc.exconly()


def test_create_campaign_fails_for_invalid_prompts_when_prompts_missing_text(
    client, db_developer_user, db_advertiser
):
    # Arrange
    new_campaign = _get_create_campaign_skeleton(db_advertiser)
    new_campaign["prompts"] = [dict(type="single_choice", choices=["a", "b", "c"], text="")]

    # Act
    with client.user_request_context(db_developer_user):
        with pytest.raises(InvalidPromptsException) as exc:
            CreateCampaign().mutate("info", reward_model=RewardModels.assets, **new_campaign)

    # Assert
    assert "must have a text" in exc.exconly()


def test_set_campaign_report_summary(client, db_developer_user, db_campaign):
    assert db_campaign.report_summary is None

    with client.user_request_context(db_developer_user):
        SetReportSummary().mutate("info", id=db_campaign.id, summary="Summary")

    assert db_campaign.report_summary == "Summary"

    with client.user_request_context(db_developer_user):
        SetReportSummary().mutate("info", id=db_campaign.id, summary="")

    assert db_campaign.report_summary is None
