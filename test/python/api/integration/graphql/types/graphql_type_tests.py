import mock
from graphql.type.definition import GraphQLScalarType

from takumi.gql.schema import schema
from takumi.gql.types.campaign import Campaign, CampaignConnection
from takumi.gql.types.insight import InsightConnection
from takumi.models import Currency
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.utils import uuid4_str


def resolve_all_fields_for_a_type(type_name, item, skip=None):
    type_map = schema.get_type_map()
    item_type = type_map.get(type_name)

    if skip is None:
        skip = []

    mock_info = mock.Mock()

    for name, field in item_type.fields.items():
        if name == "id" or name in skip:
            continue

        mock_info.field_name = name
        value = field.resolver(item, mock_info)

        # Test serialisation for scalars
        if value is not None and isinstance(field.type, GraphQLScalarType):
            field.type.serialize(value)


def test_campaign_type_resolve_accessible_data_non_brand_profile_user(
    db_campaign, db_session, db_post, db_campaign_metric
):
    db_campaign_metric.assets = db_campaign.units
    db_campaign.posts_with_stats.append(db_post)
    db_session.commit()

    accessible_data = Campaign.resolve_accessible_data(db_campaign, "info")
    assert accessible_data["id"] == db_campaign.id
    assert accessible_data["name"] == db_campaign.name
    assert accessible_data["impressions"] == 0
    assert accessible_data["engagement_rate"] == 0
    assert accessible_data["benchmark"] == 0
    assert accessible_data["type"] == "assets"
    assert accessible_data["reach"] is None
    assert accessible_data["assets"] == 10
    assert accessible_data["budget"] == "£1,000"


def test_campaign_type_resolve_accessible_data_no_campaign_metric(db_campaign):
    accessible_data = Campaign.resolve_accessible_data(db_campaign, "info")
    assert accessible_data["id"] == db_campaign.id
    assert accessible_data["name"] == db_campaign.name
    assert accessible_data["impressions"] == 0
    assert accessible_data["engagement_rate"] == 0
    assert accessible_data["benchmark"] == 0
    assert accessible_data["type"] == "assets"
    assert accessible_data["reach"] == 0
    assert accessible_data["assets"] == 0
    assert accessible_data["budget"] == "£1,000"


def test_campaign_type_resolve_price_brand_profile_budget_true(
    db_campaign, db_brand_profile_user, client
):
    advertiser_config = db_campaign.advertiser.advertiser_config
    advertiser_config.budget = True

    with client.user_request_context(db_brand_profile_user):
        result = Campaign.resolve_price(db_campaign, "info")
    assert (
        result.formatted_value
        == Currency(amount=db_campaign.price, currency=db_campaign.market.currency).formatted_value
    )


def test_campaign_type_resolve_price_brand_profile_budget_false(
    db_campaign, db_brand_profile_user, client
):
    advertiser_config = db_campaign.advertiser.advertiser_config
    advertiser_config.budget = False

    with client.user_request_context(db_brand_profile_user):
        result = Campaign.resolve_price(db_campaign, "info")
    assert result is None


def test_campaign_type_resolve_impressions_brand_profile_impressions_true(
    db_campaign, db_brand_profile_user, client
):
    advertiser_config = db_campaign.advertiser.advertiser_config
    advertiser_config.impressions = True

    with client.user_request_context(db_brand_profile_user):
        result = Campaign.resolve_impressions(db_campaign, "info")
    assert result == db_campaign.impressions


def test_campaign_type_resolve_impressions_brand_profile_impressions_false(
    db_campaign, db_brand_profile_user, client
):
    advertiser_config = db_campaign.advertiser.advertiser_config
    advertiser_config.impressions = False

    with client.user_request_context(db_brand_profile_user):
        result = Campaign.resolve_impressions(db_campaign, "info")
    assert result is None


def test_campaign_type_resolve_reward_model_brand_profile_campaign_type_true(
    db_campaign, db_brand_profile_user, client
):
    advertiser_config = db_campaign.advertiser.advertiser_config
    advertiser_config.campaign_type = True

    with client.user_request_context(db_brand_profile_user):
        result = Campaign.resolve_reward_model(db_campaign, "info")
    assert result == db_campaign.reward_model


def test_campaign_type_resolve_reward_model_brand_profile_campaign_type_false(
    db_campaign, db_brand_profile_user, client
):
    advertiser_config = db_campaign.advertiser.advertiser_config
    advertiser_config.campaign_type = False

    with client.user_request_context(db_brand_profile_user):
        result = Campaign.resolve_reward_model(db_campaign, "info")
    assert result is None


def test_campaign_type_engagement_model_brand_profile_engagement_true(
    db_campaign, db_brand_profile_user, client
):
    advertiser_config = db_campaign.advertiser.advertiser_config
    advertiser_config.engagement_rate = True

    with client.user_request_context(db_brand_profile_user):
        result = Campaign.resolve_engagement(db_campaign, "info")
    assert result == db_campaign.engagement


def test_campaign_type_engagement_model_brand_profile_engagement_false(
    db_campaign, db_brand_profile_user, client
):
    advertiser_config = db_campaign.advertiser.advertiser_config
    advertiser_config.engagement_rate = False

    with client.user_request_context(db_brand_profile_user):
        result = Campaign.resolve_engagement(db_campaign, "info")
    assert result is None


def test_campaign_type_campaign_highlights_brand_profile_engagement_true(
    db_campaign, db_brand_profile_user, client
):
    advertiser_config = db_campaign.advertiser.advertiser_config
    advertiser_config.engagement_rate = True

    with client.user_request_context(db_brand_profile_user):
        result = Campaign.resolve_campaign_highlights(db_campaign, "info")

    assert result["engagement_rate"] == 0
    assert result["engagement_rate_static"] == 0
    assert result["engagement_rate_story"] == 0
    assert result["engagement_rate_static_from_total"] == 0
    assert result["engagement_rate_story_from_total"] == 0


def test_campaign_type_campaign_highlights_brand_profile_engagement_false(
    db_campaign, db_brand_profile_user, client
):
    advertiser_config = db_campaign.advertiser.advertiser_config
    advertiser_config.engagement_rate = False

    with client.user_request_context(db_brand_profile_user):
        result = Campaign.resolve_campaign_highlights(db_campaign, "info")

    assert result["engagement_rate"] is None
    assert result["engagement_rate_static"] is None
    assert result["engagement_rate_story"] is None
    assert result["engagement_rate_static_from_total"] is None
    assert result["engagement_rate_story_from_total"] is None


def test_campaign_type_resolve_accessible_data_brand_profile_user_all_disabled(
    db_campaign,
    db_campaign_metric,
    db_session,
    db_post,
    db_brand_profile_user,
    client,
):
    db_campaign_metric.assets = db_campaign.units
    db_campaign.posts_with_stats.append(db_post)
    db_session.commit()
    expected_result = {
        "id": db_campaign.id,
        "name": db_campaign.name,
        "impressions": None,
        "engagement_rate": None,
        "benchmark": None,
        "type": None,
        "reach": None,
        "assets": db_campaign.units,
        "budget": None,
    }

    with client.user_request_context(db_brand_profile_user):
        accessible_data = Campaign.resolve_accessible_data(db_campaign, "info")
    assert expected_result == accessible_data == expected_result


def test_campaign_type_resolve_accessible_data_brand_profile_user_all_enable(
    db_campaign,
    db_session,
    db_post,
    db_brand_profile_user,
    db_campaign_metric,
    client,
):
    advertiser_config = db_campaign.advertiser.advertiser_config
    advertiser_config.budget = True
    advertiser_config.benchmarks = True
    advertiser_config.campaign_type = True
    advertiser_config.engagement_rate = True
    advertiser_config.impressions = True

    db_campaign_metric.assets = db_campaign.units
    db_campaign.posts_with_stats.append(db_post)
    db_session.commit()
    expected_result = {
        "id": db_campaign.id,
        "name": db_campaign.name,
        "impressions": 0,
        "engagement_rate": 0,
        "benchmark": 0,
        "type": "assets",
        "reach": None,
        "assets": 10,
        "budget": "£1,000",
    }

    with client.user_request_context(db_brand_profile_user):
        accessible_data = Campaign.resolve_accessible_data(db_campaign, "info")
    assert expected_result == accessible_data == expected_result


def test_campaign_type_resolve_accessible_data_brand_profile_user_campaign_type(
    db_campaign,
    db_campaign_metric,
    db_session,
    db_post,
    db_brand_profile_user,
    client,
):
    advertiser_config = db_campaign.advertiser.advertiser_config
    advertiser_config.campaign_type = True

    db_campaign.posts_with_stats.append(db_post)
    db_campaign.reward_model = "reach"
    db_session.commit()
    expected_result = {
        "id": db_campaign.id,
        "name": db_campaign.name,
        "impressions": None,
        "engagement_rate": None,
        "benchmark": None,
        "type": "reach",
        "reach": 0,
        "assets": None,
        "budget": None,
    }

    with client.user_request_context(db_brand_profile_user):
        accessible_data = Campaign.resolve_accessible_data(db_campaign, "info")
    assert expected_result == accessible_data == expected_result


def test_campaign_connection_type_resolve_total_campaigns_data_manager(
    account_manager, client, db_campaign, db_region
):
    with client.user_request_context(account_manager):
        response = CampaignConnection.resolve_total_campaigns_data(
            "root", "info", region_id=db_region.id
        )

    assert response["total_campaigns"] == 1
    assert response["total_creators"] == 0
    assert response["total_impressions"] == 0


def test_campaign_connection_type_resolve_total_campaigns_data_brand(
    db_brand_profile_user, client, db_campaign, db_region
):
    with client.user_request_context(db_brand_profile_user):
        response = CampaignConnection.resolve_total_campaigns_data(
            "root", "info", region_id=db_region.id
        )

    assert response["total_campaigns"] == 1
    assert response["total_creators"] == 0
    assert response["total_impressions"] == 0


def test_campaign_connection_type_resolve_total_campaigns_data_with_no_existing_campaigns(
    db_brand_profile_user, client, db_campaign, db_region
):
    with client.user_request_context(db_brand_profile_user):
        response = CampaignConnection.resolve_total_campaigns_data(
            "root", "info", advertiser_industries_ids=[uuid4_str()], region_id=db_region.id
        )

    assert response["total_campaigns"] == 0
    assert response["total_creators"] == 0
    assert response["total_impressions"] == 0


def test_graphql_campaign_type_fields(db_campaign, db_post):
    resolve_all_fields_for_a_type("Campaign", db_campaign)


def test_graphql_campaign_type_fields_cash(db_cash_campaign, db_post):
    db_post.campaign = db_cash_campaign
    resolve_all_fields_for_a_type("Campaign", db_cash_campaign)


def test_graphql_campaign_type_fields_reach(db_reach_campaign, db_post):
    db_post.campaign = db_reach_campaign
    resolve_all_fields_for_a_type("Campaign", db_reach_campaign)


def test_graphql_gig_type_fields_assets(db_gig):
    resolve_all_fields_for_a_type("Gig", db_gig)


def test_graphql_gig_type_fields_reach(
    db_reach_gig, db_submission, db_reach_campaign, db_post, db_session
):
    db_submission.gig = db_reach_gig

    db_session.commit()

    resolve_all_fields_for_a_type("Gig", db_reach_gig)


def test_graphql_influencer_type_fields_db_influencer(db_influencer):
    resolve_all_fields_for_a_type("Influencer", db_influencer, skip=["isSignedUp"])


def test_graphql_influencer_type_fields_es_influencer(es_influencer):
    resolve_all_fields_for_a_type("Influencer", es_influencer, skip=["isSignedUp"])


def test_graphql_offer_type_fields(db_offer, db_post):
    resolve_all_fields_for_a_type("Offer", db_offer, skip=["rewardPerPost"])


def test_graphql_offer_type_fields_payable_offer(db_payable_offer, db_post):
    resolve_all_fields_for_a_type("Offer", db_payable_offer, skip=["rewardPerPost"])


def test_graphql_post_type_fields(db_post):
    resolve_all_fields_for_a_type("Post", db_post, skip=["gigs", "step"])


def test_graphql_advertiser_type_fields(db_advertiser):
    resolve_all_fields_for_a_type("Advertiser", db_advertiser, skip=["campaigns"])


def test_graphql_payment_type_fields(db_payment):
    resolve_all_fields_for_a_type("Payment", db_payment, skip=["dashboardLink"])


def test_graphql_user_type_fields_advertiser_user(db_advertiser_user):
    resolve_all_fields_for_a_type("User", db_advertiser_user)


def test_graphql_user_type_fields_influencer_user(db_influencer_user):
    resolve_all_fields_for_a_type("User", db_influencer_user)


def test_graphql_influencer_campaign_and_offer_type_fields(db_influencer, db_campaign, db_offer):
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    resolve_all_fields_for_a_type("InfluencerCampaignAndOffer", db_influencer.campaigns.first())


def test_graphql_tax_form_number_fields(db_tax_form):
    resolve_all_fields_for_a_type("TaxForm", db_tax_form)


def test_graphql_insight_resolve_insights_count(
    db_post_insight, db_story_insight, client, db_developer_user
):
    with client.user_request_context(db_developer_user):
        insights_count = InsightConnection.resolve_insights_count("root", "info", kwargs={})

    expected_result = 2
    assert insights_count == expected_result
