# encoding=utf-8
import datetime as dt

import mock
import pytest
from freezegun import freeze_time

from takumi.models import OfferEvent
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.campaign import RewardModels
from takumi.models.offer import STATES as OFFER_STATES
from takumi.rewards import RewardCalculator
from takumi.services.exceptions import (
    CampaignFullyReservedException,
    InfluencerNotEligibleException,
    InfluencerOnCooldownForAdvertiserException,
    OfferAlreadyClaimed,
    OfferNotReservableException,
    OfferRewardChangedException,
    ServiceException,
)
from takumi.services.offer import OfferService


def test_offer_service_get_by_id(db_offer):
    offer = OfferService.get_by_id(db_offer.id)
    assert offer == db_offer


def test_offer_service_create_offer_fails_if_influencer_on_cooldown_for_advertiser(
    db_session, db_influencer, db_campaign, campaign_factory, offer_factory
):
    # Setup a previous offer for influencer with same advertiser
    prev_campaign = campaign_factory()
    prev_campaign.state = CAMPAIGN_STATES.COMPLETED
    prev_campaign.advertiser = db_campaign.advertiser
    prev_offer = offer_factory()
    prev_offer.influencer = db_influencer
    prev_offer.campaign = prev_campaign
    prev_offer.state = OFFER_STATES.ACCEPTED
    prev_offer.accepted = dt.datetime.now(dt.timezone.utc)
    db_session.add(prev_offer)
    db_session.commit()

    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_campaign.advertiser.influencer_cooldown = 1

    # Act
    with pytest.raises(InfluencerOnCooldownForAdvertiserException) as exc:
        OfferService.create(db_campaign.id, db_influencer.id)

    # Assert
    assert "on cooldown" in exc.exconly()


@freeze_time(dt.datetime(2019, 1, 10, tzinfo=dt.timezone.utc))
def test_offer_service_create_offer_fails_if_deadline_passed(db_influencer, db_campaign, db_post):
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_post.deadline = dt.datetime(2019, 1, 11, tzinfo=dt.timezone.utc)
    db_post.submission_deadline = dt.datetime(2019, 1, 9, tzinfo=dt.timezone.utc)

    with pytest.raises(
        ServiceException, match="A submission deadline for the campaign has already passed"
    ):
        OfferService.create(db_campaign.id, db_influencer.id)

    db_post.deadline = dt.datetime(2019, 1, 9, tzinfo=dt.timezone.utc)
    db_post.submission_deadline = dt.datetime(2019, 1, 11, tzinfo=dt.timezone.utc)

    with pytest.raises(ServiceException, match="A deadline for the campaign has already passed"):
        OfferService.create(db_campaign.id, db_influencer.id)

    db_post.deadline = dt.datetime(2019, 1, 12, tzinfo=dt.timezone.utc)
    db_post.submission_deadline = dt.datetime(2019, 1, 11, tzinfo=dt.timezone.utc)

    OfferService.create(db_campaign.id, db_influencer.id)


def test_offer_service_create_offer_fails_if_campaign_not_reservable(db_influencer, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_campaign.units = 0  # Campaign not reservable if units are 0

    # Act
    with pytest.raises(CampaignFullyReservedException) as exc:
        OfferService.create(db_campaign.id, db_influencer.id)

    # Assert
    assert "Campaign is already fully reserved" in exc.exconly()


def test_offer_service_create_offer_fails_if_no_target_available(db_influencer, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_influencer.state = "disabled"  # Disabled influencers cannot be targeted

    # Act
    with pytest.raises(InfluencerNotEligibleException) as exc:
        OfferService.create(db_campaign.id, db_influencer.id)

    # Assert
    assert "Influencer is not eligible" in exc.exconly()


def test_offer_service_create_offer_success(db_influencer, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    expected_reward = RewardCalculator(campaign=db_campaign).calculate_reward_for_influencer(
        db_influencer
    )

    # Act
    res = OfferService.create(db_campaign.id, db_influencer.id)

    # Assert
    assert res.campaign_id == db_campaign.id
    assert res.influencer_id == db_influencer.id
    assert res.reward == expected_reward
    assert res.followers_per_post == db_influencer.instagram_account.followers


def test_create_offer_does_not_take_posts_per_influencer_into_account(
    monkeypatch, db_influencer, db_campaign
):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.post_count", mock.PropertyMock(return_value=3)
    )
    db_influencer.instagram_account.followers = 1000

    # Act
    result = OfferService.create(db_campaign.id, db_influencer.id)

    # Assert
    assert result.followers_per_post == 1000


def test_offer_service_create_offer_for_apply_first_campaign_creates_a_pending_offer(
    elasticsearch, db_influencer, db_campaign
):
    # Arrange
    db_campaign.apply_first = True
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED

    # Act
    offer = OfferService.create(db_campaign.id, db_influencer.id)

    # Assert
    assert offer.state == OFFER_STATES.PENDING


def test_offer_service_create_offer_for_non_apply_first_campaign_creates_an_invited_offer(
    db_influencer, db_campaign
):
    # Arrange
    db_campaign.apply_first = False
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED

    # Act
    offer = OfferService.create(db_campaign.id, db_influencer.id)

    # Assert
    assert offer.state == OFFER_STATES.INVITED


def test_offer_update_reward_updates_the_reward(db_offer):
    # Arrange
    assert db_offer.reward != 1337

    # Act
    with OfferService(db_offer) as service:
        service.update_reward(1337)

    # Assert
    assert db_offer.reward == 1337


def test_offer_update_reward_raises_exception_if_claimed(db_session, db_payable_offer, db_payment):
    # Arrange
    db_payment.successful = True
    db_session.commit()

    # Act
    with pytest.raises(OfferAlreadyClaimed, match="Offer has already been claimed"):
        OfferService(db_payable_offer).update_reward(1337)


def test_offer_reserve_updates_the_reward_and_throws_exception(
    db_session, db_offer, db_reach_campaign, monkeypatch
):
    # Arrange
    db_reach_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.state = OFFER_STATES.INVITED
    db_offer.campaign = db_reach_campaign
    db_session.commit()
    monkeypatch.setattr(
        "takumi.rewards.RewardCalculator.calculate_reward_for_influencer", lambda *args: 1337
    )

    # Act
    with pytest.raises(OfferRewardChangedException) as exc:
        with mock.patch("takumi.services.offer.OfferService.update_reward") as mock_update_reward:
            OfferService(db_offer).reserve()

    # Assert
    assert mock_update_reward.called
    assert (
        "There's limited space left on this campaign, so we're not able to offer the full reward"
        in exc.exconly()
    )


@freeze_time(dt.datetime(2017, 1, 5))
def test_offer_reserve_prevents_reserving_if_deadline_passed_in_post(
    db_session, db_offer, db_campaign, db_post
):
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED

    # Deadline in the past
    db_post.deadline = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    db_session.commit()

    with OfferService(db_offer) as service:
        with pytest.raises(OfferNotReservableException) as exc:
            service.reserve()

    assert "Deadline has already passed" in exc.exconly()

    # Deadline in the future
    db_post.deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
    db_session.commit()

    with OfferService(db_offer) as service:
        service.reserve()


def test_offer_force_reserve_success(db_session, db_offer, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.state = OFFER_STATES.REJECTED
    db_session.commit()

    # Act
    with OfferService(db_offer) as service:
        service.force_reserve()

    # Assert
    assert db_offer.state == OFFER_STATES.ACCEPTED


def test_offer_request_participation_success(db_session, db_offer, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_offer.state = OFFER_STATES.PENDING
    db_session.commit()

    # Act
    with OfferService(db_offer) as service:
        service.request_participation()

    # Assert
    assert db_offer.state == OFFER_STATES.REQUESTED


def test_offer_answer_validation(db_session, db_offer, db_campaign):
    # Arrange
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_campaign.prompts = [
        dict(text="text question", type="text"),
        dict(text="multi choice question", type="multiple_choice", choices=["X", "Y", "Z"]),
        dict(text="Confirm", type="confirmation", choices=["A", "B", "C"]),
    ]
    db_offer.state = OFFER_STATES.PENDING
    db_session.commit()

    # Act
    with pytest.raises(Exception, match="You need to answer all the prompts"):
        with OfferService(db_offer) as service:
            service.request_participation(answers=None)

    with pytest.raises(Exception, match="You need to answer all the prompts"):
        with OfferService(db_offer) as service:
            service.request_participation(answers=[])

    with pytest.raises(Exception, match="All confirmations need to be accepted"):
        with OfferService(db_offer) as service:
            service.request_participation(
                answers=[
                    dict(prompt="Confirm", answer=["A"]),
                    dict(prompt="multi choice question", answer=["X", "Z"]),
                    dict(prompt="text question", answer=["abc"]),
                ]
            )

    with pytest.raises(Exception, match="You need to answer 'text question'"):
        with OfferService(db_offer) as service:
            service.request_participation(
                answers=[
                    dict(prompt="Confirm", answer=["A", "B", "C"]),
                    dict(prompt="multi choice question", answer=["X", "Z"]),
                    dict(prompt="text question", answer=[""]),
                ]
            )

    with pytest.raises(Exception, match="You need to answer 'multi choice question'"):
        with OfferService(db_offer) as service:
            service.request_participation(
                answers=[
                    dict(prompt="Confirm", answer=["A", "B", "C"]),
                    dict(prompt="multi choice question", answer=[]),
                    dict(prompt="text question", answer=["some answer"]),
                ]
            )

    with OfferService(db_offer) as service:
        service.request_participation(
            answers=[
                dict(prompt="Confirm", answer=["A", "B", "C"]),
                dict(prompt="multi choice question", answer=["X"]),
                dict(prompt="text question", answer=["some answer"]),
            ]
        )


def test_offer_get_push_notifications_returns_all_events_in_correct_order(db_session, db_offer):
    # Arrange
    dt_1 = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    dt_2 = dt.datetime.now(dt.timezone.utc)
    dt_3 = dt.datetime.now(dt.timezone.utc)
    dt_4 = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)

    oe_1 = OfferEvent(type="send_push_notification", created=dt_1, offer_id=db_offer.id)
    oe_2 = OfferEvent(type="something_else", created=dt_2, offer_id=db_offer.id)
    oe_3 = OfferEvent(type="send_push_notification", created=dt_3, offer_id=db_offer.id)
    oe_4 = OfferEvent(type="send_push_notification", created=dt_4, offer_id=db_offer.id)
    db_session.add_all([oe_1, oe_2, oe_3, oe_4])

    # Act
    res = OfferService.get_push_notifications(db_offer.id)

    # Assert
    assert len(res) == 3
    assert res == [(dt_3,), (dt_1,), (dt_4,)]


def test_get_revoke_event_returns_correct_event(db_offer, offer_event_factory):
    # Arrange
    offer_event = offer_event_factory(
        offer=db_offer, created=dt.datetime.now(dt.timezone.utc), type="revoke"
    )
    db_offer.events = [
        offer_event,
        offer_event_factory(
            offer=db_offer,
            created=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
            type="revoke",
        ),
        offer_event_factory(
            offer=db_offer,
            created=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1),
            type="create_invite",
        ),
    ]

    # Act
    revoke_event = OfferService.get_revoke_event(db_offer.id)

    # Assert
    assert revoke_event == offer_event


def test_get_revoke_event_returns_none_when_event_not_found(db_offer):
    # Arrange
    db_offer.events = []

    # Act
    revoke_event = OfferService.get_revoke_event(db_offer.id)

    # Assert
    assert revoke_event is None


def test_get_rejected_date_returns_correct_date_scalar(db_offer, offer_event_factory):
    # Arrange
    dt1 = dt.datetime.now(dt.timezone.utc)
    dt2 = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    dt3 = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
    db_offer.events = [
        offer_event_factory(offer=db_offer, created=dt1, type="reject"),
        offer_event_factory(offer=db_offer, created=dt2, type="reject"),
        offer_event_factory(offer=db_offer, created=dt3, type="create_invite"),
    ]

    # Act
    reject_date = OfferService.get_rejected_date(db_offer.id)

    # Assert
    assert reject_date == dt1


def test_get_rejected_date_returns_none_when_event_not_found(db_offer):
    # Arrange
    db_offer.events = []

    # Act
    reject_date = OfferService.get_rejected_date(db_offer.id)

    # Assert
    assert reject_date is None


def test_revert_rejection_reverts_to_previous_state(db_session, db_offer, db_campaign):
    db_offer.state = OFFER_STATES.REQUESTED
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_campaign.apply_first = True
    db_session.commit()

    with freeze_time(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)):
        with OfferService(db_offer) as service:
            service.revoke()
        assert db_offer.state == OFFER_STATES.REVOKED

    with freeze_time(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=4)):
        with OfferService(db_offer) as service:
            service.revert_rejection()
        assert db_offer.state == OFFER_STATES.REQUESTED

        with OfferService(db_offer) as service:
            service.accept_request()
        assert db_offer.state == OFFER_STATES.ACCEPTED

    with freeze_time(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)):
        with OfferService(db_offer) as service:
            service.revoke()
        assert db_offer.state == OFFER_STATES.REVOKED

    with freeze_time(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)):
        with OfferService(db_offer) as service:
            service.revert_rejection()
        assert db_offer.state == OFFER_STATES.ACCEPTED


def test_revert_rejection_doesnt_overfill_asset_campaign(db_session, db_campaign, offer_factory):
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_campaign.apply_first = True
    db_session.commit()

    offer = offer_factory(campaign=db_campaign, state=OFFER_STATES.ACCEPTED)
    db_session.add(offer)
    db_session.commit()

    with OfferService(offer) as service:
        service.revoke()

    # Fill the campaign
    other_offers = [
        offer_factory(campaign=db_campaign, state=OFFER_STATES.ACCEPTED)
        for _ in range(db_campaign.units)
    ]
    db_session.add_all(other_offers)
    db_session.commit()

    with pytest.raises(Exception, match="Not enough space on the campaign to revert rejection"):
        OfferService(offer).revert_rejection()


def test_revert_rejection_doesnt_overfill_reach_campaign(db_session, db_campaign, offer_factory):
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED
    db_campaign.reward_model = RewardModels.reach
    db_campaign.units = 1_000_000
    db_campaign.apply_first = True
    db_session.commit()

    offer = offer_factory(
        campaign=db_campaign, state=OFFER_STATES.ACCEPTED, followers_per_post=200_000
    )
    db_session.add(offer)
    db_session.commit()

    with OfferService(offer) as service:
        service.revoke()

    # Fill the campaign
    other_offers = [
        offer_factory(campaign=db_campaign, state=OFFER_STATES.ACCEPTED, followers_per_post=99000)
        for _ in range(10)
    ]
    db_session.add_all(other_offers)
    db_session.commit()

    with pytest.raises(Exception, match="Not enough space on the campaign to revert rejection"):
        OfferService(offer).revert_rejection()

    # Check that it works with low enough followers
    progress = db_campaign.fund.get_progress()
    available = progress["total"] - progress["reserved"]
    assert available == 10000

    offer.followers_per_post = available
    db_session.commit()

    with OfferService(offer) as service:
        service.revert_rejection()

    assert offer.state == OFFER_STATES.ACCEPTED
