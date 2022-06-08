from takumi.models.campaign import RewardModels


def test_targeting_absolute_min_followers(db_session, db_campaign):
    db_campaign.reward_model = RewardModels.assets
    db_session.commit()

    assert db_campaign.targeting.absolute_min_followers == 1000

    db_campaign.reward_model = RewardModels.reach
    db_session.commit()

    assert db_campaign.targeting.absolute_min_followers == 15_000
