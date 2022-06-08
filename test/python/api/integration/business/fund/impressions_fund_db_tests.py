import pytest

from takumi.models import Influencer, InstagramAccount, PostInsight, User
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.insight import STATES as INSIGHT_STATES
from takumi.services.exceptions import CampaignFullyReservedException
from takumi.services.offer import OfferService


def get_influencer(session, ratio):
    user = User(role_name="influencer")
    influencer = Influencer(state="verified", user=user)
    account = InstagramAccount(
        ig_media_id=str(ratio),
        token="token",
        followers=100_000,
        ig_user_id=str(ratio),
        ig_username=f"ratio{ratio}",
        influencer=influencer,
        impressions_ratio=ratio,
    )

    session.add_all([user, influencer, account])
    session.commit()

    return influencer


@pytest.fixture(scope="function")
def db_influencer_50k(db_session):
    yield get_influencer(db_session, 0.5)


@pytest.fixture(scope="function")
def db_influencer_30k(db_session):
    yield get_influencer(db_session, 0.3)


@pytest.fixture(scope="function")
def db_influencer_20k(db_session):
    yield get_influencer(db_session, 0.2)


@pytest.fixture(scope="function")
def db_influencer_10k(db_session):
    yield get_influencer(db_session, 0.1)


def test_impressions_fund_uses_estimated_influencer_estimated_impressions(
    db_session,
    db_impressions_campaign,
    db_impressions_post,
    db_influencer_50k,
    db_influencer_30k,
    db_influencer_20k,
    db_influencer_10k,
):
    db_impressions_campaign.units = 100_000
    db_impressions_campaign.state = CAMPAIGN_STATES.LAUNCHED

    db_session.commit()

    assert db_impressions_campaign.fund._remaining_impressions == 100_000

    offer_20k = OfferService.create(
        db_impressions_campaign.id, db_influencer_20k.id, skip_targeting=True
    )

    assert db_impressions_campaign.fund._remaining_impressions == 100_000

    with OfferService(offer_20k) as service:
        service.reserve()

    assert db_impressions_campaign.fund._remaining_impressions == 80000

    offer_50k = OfferService.create(
        db_impressions_campaign.id, db_influencer_50k.id, skip_targeting=True
    )

    assert db_impressions_campaign.fund._remaining_impressions == 80000

    with OfferService(offer_50k) as service:
        service.reserve()

    assert db_impressions_campaign.fund._remaining_impressions == 30000

    offer_30k = OfferService.create(
        db_impressions_campaign.id, db_influencer_30k.id, skip_targeting=True
    )
    with OfferService(offer_30k) as service:
        service.reserve()

    with pytest.raises(CampaignFullyReservedException):
        OfferService.create(db_impressions_campaign.id, db_influencer_10k.id, skip_targeting=True)


def test_impressions_fund_opens_up_space_if_estimated_impressions_was_too_high(
    db_session,
    db_impressions_campaign,
    db_impressions_post,
    db_influencer_50k,
    db_influencer_30k,
    db_influencer_20k,
    db_influencer_10k,
    gig_factory,
):
    db_impressions_campaign.units = 100_000
    db_impressions_campaign.state = CAMPAIGN_STATES.LAUNCHED

    db_session.commit()

    offer_50k = OfferService.create(
        db_impressions_campaign.id, db_influencer_50k.id, skip_targeting=True
    )
    offer_30k = OfferService.create(
        db_impressions_campaign.id, db_influencer_30k.id, skip_targeting=True
    )
    offer_20k = OfferService.create(
        db_impressions_campaign.id, db_influencer_20k.id, skip_targeting=True
    )

    with OfferService(offer_50k) as service:
        service.reserve()
    with OfferService(offer_30k) as service:
        service.reserve()
    with OfferService(offer_20k) as service:
        service.reserve()

    assert not db_impressions_campaign.fund.is_reservable()
    assert db_impressions_campaign.fund._remaining_impressions == 0

    gig = gig_factory(offer=offer_50k)
    gig.insight = PostInsight(from_other_impressions=30000, state=INSIGHT_STATES.APPROVED)
    db_session.add(gig)
    db_session.commit()

    assert db_impressions_campaign.fund.is_reservable()
    assert db_impressions_campaign.fund._remaining_impressions == 20000


def test_impressions_fund_progress_uses_submitted_impressions(
    db_session,
    db_impressions_campaign,
    db_impressions_post,
    db_influencer_50k,
    db_influencer_30k,
    gig_factory,
):
    db_impressions_campaign.units = 100_000
    db_impressions_campaign.state = CAMPAIGN_STATES.LAUNCHED

    db_session.commit()

    progress = db_impressions_campaign.fund.get_progress()
    assert progress["total"] == 100_000
    assert progress["reserved"] == 0
    assert progress["submitted"] == 0

    offer_50k = OfferService.create(
        db_impressions_campaign.id, db_influencer_50k.id, skip_targeting=True
    )
    offer_30k = OfferService.create(
        db_impressions_campaign.id, db_influencer_30k.id, skip_targeting=True
    )

    with OfferService(offer_50k) as service:
        service.reserve()
    with OfferService(offer_30k) as service:
        service.reserve()

    progress = db_impressions_campaign.fund.get_progress()
    assert progress["total"] == 100_000
    assert progress["reserved"] == 80000
    assert progress["submitted"] == 0

    gig = gig_factory(offer=offer_50k, is_verified=True, state=GIG_STATES.APPROVED)
    db_session.add(gig)
    db_session.commit()

    progress = db_impressions_campaign.fund.get_progress()
    assert progress["total"] == 100_000
    assert progress["reserved"] == 80000
    assert progress["submitted"] == 50000
