import datetime as dt

import pytest
from flask import current_app

from takumi.constants import MIN_INSTAGRAM_POSTS
from takumi.models import Influencer, Notification, Offer, Payment
from takumi.utils import uuid4_str


@pytest.fixture()
def impressions_influencers(
    db_session, db_campaign, influencer_factory, instagram_account_factory, offer_factory
):
    influencer1 = influencer_factory(
        instagram_account=instagram_account_factory(
            ig_user_id="123",
            ig_username="a",
            followers=10000,
            impressions_ratio=0.20,
        ),
    )
    influencer2 = influencer_factory(
        instagram_account=instagram_account_factory(
            ig_user_id="456",
            ig_username="b",
            followers=10000,
            impressions_ratio=0.30,
        ),
    )
    influencer3 = influencer_factory(
        instagram_account=instagram_account_factory(
            ig_user_id="789",
            ig_username="c",
            followers=10000,
            impressions_ratio=None,  # Default 0.25
        ),
    )

    db_session.add_all([influencer1, influencer2, influencer3])
    db_session.commit()


def test_querying_by_estimated_expressions(app, impressions_influencers):
    q = Influencer.query.filter(Influencer.estimated_impressions > 2999)
    assert q.count() == 1
    assert q.first().username == "b"

    assert Influencer.query.filter(Influencer.estimated_impressions > 2499).count() == 2
    assert Influencer.query.filter(Influencer.estimated_impressions > 1999).count() == 3


def test_default_impression_ratio(app, impressions_influencers):
    q = Influencer.query.filter(Influencer.estimated_impressions == 2500)
    assert q.count() == 1
    assert q.first().username == "c"
    assert q.first().impressions_ratio is None


def test_influencer_is_eligible(db_influencer):
    def _reset_influencer():
        db_influencer.state == Influencer.STATES.VERIFIED
        db_influencer.instagram_account.followers = current_app.config["MINIMUM_FOLLOWERS"]
        db_influencer.instagram_account.ig_is_private = False
        db_influencer.instagram_account.media_count = MIN_INSTAGRAM_POSTS
        db_influencer.is_signed_up = True
        assert db_influencer.is_eligible

    db_influencer.is_signed_up = False
    assert not db_influencer.is_eligible
    _reset_influencer()
    db_influencer.instagram_account.followers = 0
    assert not db_influencer.is_eligible
    _reset_influencer()
    db_influencer.instagram_account.ig_is_private = True
    assert not db_influencer.is_eligible
    _reset_influencer()
    db_influencer.instagram_account.media_count = MIN_INSTAGRAM_POSTS - 1
    assert not db_influencer.is_eligible
    _reset_influencer()
    db_influencer.is_signed_up = False
    assert not db_influencer.is_eligible


def test_influencer_matches_any_of_interest_ids(db_influencer):
    assert db_influencer.matches_any_of_interest_ids(db_influencer.interest_ids)
    assert db_influencer.matches_any_of_interest_ids([])
    assert db_influencer.matches_any_of_interest_ids(None)
    assert not db_influencer.matches_any_of_interest_ids([uuid4_str()])
    assert db_influencer.matches_any_of_interest_ids([db_influencer.interest_ids[0], uuid4_str()])


def test_influencer_matches_any_of_ages(db_influencer):
    assert db_influencer.matches_any_of_ages([db_influencer.user.age])
    assert db_influencer.matches_any_of_ages([])
    assert not db_influencer.matches_any_of_ages([1000])


def test_influencer_matches_gender(db_influencer):
    db_influencer.gender = "male"
    assert db_influencer.matches_gender(None)
    assert db_influencer.matches_gender(db_influencer.user.gender)
    assert not db_influencer.matches_gender("female")


def test_influencer_matches_any_of_regions(db_influencer, db_region, region_factory):
    db_influencer.target_region = db_region

    assert db_influencer.matches_any_of_regions([db_region])
    assert db_influencer.matches_any_of_regions([])
    assert db_influencer.matches_any_of_regions(None)
    assert db_influencer.matches_any_of_regions([db_region, region_factory()])
    assert not db_influencer.matches_any_of_regions([region_factory()])


def test_influencer_matches_max_followers(db_influencer):
    db_influencer.instagram_account.followers = 40000

    # Influencer has more than max in targeting
    assert not db_influencer.matches_max_followers(39999)

    # Influencer has exact or less than the max targeted
    assert db_influencer.matches_max_followers(40000)
    assert db_influencer.matches_max_followers(40001)

    # Should match if there is no max
    assert db_influencer.matches_max_followers(None)


def test_influencer_matches_targeting(db_influencer, db_campaign, region_factory):
    assert db_influencer.matches_targeting(db_campaign.targeting)
    db_campaign.targeting.regions = [region_factory()]
    assert not db_influencer.matches_targeting(db_campaign.targeting)


def test_influencer_notification_count(
    db_session, db_influencer, db_campaign, db_device, campaign_factory
):
    db_influencer.user.device = db_device
    different_campaign = campaign_factory()

    db_session.add(different_campaign)
    db_session.commit()

    assert db_influencer.notification_count(db_campaign) == 0

    db_session.add(Notification(device=db_influencer.device, campaign=db_campaign))
    db_session.commit()
    assert db_influencer.notification_count(db_campaign) == 1

    db_session.add(Notification(device=db_influencer.device, campaign=db_campaign))
    db_session.commit()

    assert db_influencer.notification_count(db_campaign) == 2

    db_session.add(Notification(device=db_influencer.device, campaign=different_campaign))
    db_session.commit()

    assert db_influencer.notification_count(db_campaign) == 2
    assert db_influencer.notification_count(different_campaign) == 1


def test_influencer_last_notification_sent(
    db_session, db_influencer, db_campaign, db_device, campaign_factory
):
    db_influencer.user.device = db_device
    different_campaign = campaign_factory()

    db_session.add(different_campaign)
    db_session.commit()

    assert db_influencer.last_notification_sent(db_campaign) == None

    notification = Notification(device=db_influencer.device, campaign=db_campaign)
    db_session.add(notification)
    db_session.commit()
    assert db_influencer.last_notification_sent(db_campaign) == notification.sent


def test_total_rewards_breakdown(db_session, db_influencer, offer_factory, payment_factory):
    offer_1: Offer = offer_factory(
        is_claimable=True,
        influencer=db_influencer,
        payable=dt.datetime.now(dt.timezone.utc),
        reward=1000,
        vat_percentage=0.19,
    )
    offer_1.payments = [
        payment_factory(
            offer=offer_1, amount=offer_1.reward, state=Payment.STATES.PAID, successful=True
        )
    ]
    offer_2: Offer = offer_factory(
        is_claimable=True,
        influencer=db_influencer,
        payable=dt.datetime.now(dt.timezone.utc),
        reward=2000,
        vat_percentage=0.24,
    )
    offer_2.payments = [
        payment_factory(
            offer=offer_2, amount=offer_2.reward, state=Payment.STATES.PAID, successful=True
        )
    ]
    db_session.add_all([offer_1, offer_2])
    db_session.commit()

    # Expected
    offer_1_net = pytest.approx(840.336134)
    offer_1_vat = pytest.approx(159.663866)

    offer_2_net = pytest.approx(1612.903225)
    offer_2_vat = pytest.approx(387.096775)

    total_net = pytest.approx(840.336134 + 1612.903225)
    total_vat = pytest.approx(159.663866 + 387.096775)

    # Actual
    assert offer_1.reward_breakdown["total_value"] == 1000
    assert offer_1.reward_breakdown["net_value"] == offer_1_net
    assert offer_1.reward_breakdown["vat_value"] == offer_1_vat

    assert offer_2.reward_breakdown["total_value"] == 2000
    assert offer_2.reward_breakdown["net_value"] == offer_2_net
    assert offer_2.reward_breakdown["vat_value"] == offer_2_vat

    assert db_influencer.total_rewards_breakdown["total_value"] == 3000
    assert db_influencer.total_rewards_breakdown["net_value"] == total_net
    assert db_influencer.total_rewards_breakdown["vat_value"] == total_vat
