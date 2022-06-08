# encoding: utf-8
from takumi.gql.schema import schema
from takumi.gql.types.offer import Offer


def test_offer_type_resolve_reward_per_post(db_offer, db_campaign, db_post):
    type_map = schema.get_type_map()
    offer_type = type_map.get("Offer")
    reward_per_post_field = offer_type.fields.get("rewardPerPost")

    assert len(db_campaign.posts) == 1
    db_offer.reward = 30000

    assert reward_per_post_field.resolver(db_offer, "info").formatted_value == "£300"


def test_offer_type_resolve_reward_per_post_multipost(db_offer, db_campaign, db_post):
    type_map = schema.get_type_map()
    offer_type = type_map.get("Offer")
    reward_per_post_field = offer_type.fields.get("rewardPerPost")

    db_campaign.posts.append(db_post)
    db_campaign.posts.append(db_post)
    assert len(db_campaign.posts) == 3
    db_offer.reward = 30000

    assert reward_per_post_field.resolver(db_offer, "info").formatted_value == "£100"


def test_offer_type_resolve_influencer_metrics_manager(db_offer, client, account_manager):
    with client.user_request_context(account_manager):
        result = Offer.resolve_influencer_metrics(db_offer, "info")

    assert result["engagement_rate_static"] == 0
    assert result["engagement_rate_story"] == 0
    assert result["reach"] == 0
    assert result["total_impressions"] == 0


def test_offer_type_resolve_influencer_metrics_brand_advertiser_config_false(
    db_offer, client, db_brand_profile_user
):
    advertiser_config = db_offer.campaign.advertiser.advertiser_config
    advertiser_config.engagement_rate = False
    advertiser_config.impressions = False

    with client.user_request_context(db_brand_profile_user):
        result = Offer.resolve_influencer_metrics(db_offer, "info")

    assert result["engagement_rate_static"] is None
    assert result["engagement_rate_story"] is None
    assert result["reach"] == 0
    assert result["total_impressions"] is None


def test_offer_type_resolve_influencer_metrics_brand_advertiser_config_true(
    db_offer, client, db_brand_profile_user
):
    advertiser_config = db_offer.campaign.advertiser.advertiser_config
    advertiser_config.engagement_rate = True
    advertiser_config.impressions = True

    with client.user_request_context(db_brand_profile_user):
        result = Offer.resolve_influencer_metrics(db_offer, "info")

    assert result["engagement_rate_static"] == 0
    assert result["engagement_rate_story"] == 0
    assert result["reach"] == 0
    assert result["total_impressions"] == 0
