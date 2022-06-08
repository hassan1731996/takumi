import datetime as dt

from takumi.constants import USD_ALLOWED_BEFORE_1099
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.payment import Payment

""" Influencer.remaining_usd_before_1099 should run a query which returns the amount of cents remaining
before we need their W-9 details to issue a 1099 tax form. We don't require all influencers to enter
this information as the service has a fixed cost of a few $ per user per year. Instead we rely on this
property to check when a gig is being submitted whether the reward of that gig will push the influencer
over the USD_ALLOWED_BEFORE_1099 threshold, and invite them to fill out the tax forms.
"""


def test_influencer_remaining_usd_before_1099_offer_already_paid(
    db_offer, db_influencer, db_session
):

    db_offer.state = OFFER_STATES.ACCEPTED
    db_offer.payable = dt.datetime.now(dt.timezone.utc)
    db_offer.is_claimable = True
    payment = Payment(
        created=dt.datetime.now(dt.timezone.utc),
        type="revolut",
        offer_id=db_offer.id,
        amount=db_offer.reward,
        currency=db_offer.campaign.market.currency,
        destination="GB1234",
        successful=True,
    )
    db_session.add(payment)
    db_session.commit()

    # paid gig in the right currency
    db_offer.campaign.market_slug = "us"
    db_offer.reward = USD_ALLOWED_BEFORE_1099 + 1
    assert db_influencer.remaining_usd_before_1099 == 0
    db_offer.reward = USD_ALLOWED_BEFORE_1099 - 100
    assert db_influencer.remaining_usd_before_1099 == 100


def test_influencer_remaining_usd_before_1099_offer_payment_processing(
    db_offer, db_influencer, db_session
):
    db_offer.state = OFFER_STATES.ACCEPTED
    db_offer.payable = dt.datetime.now(dt.timezone.utc)
    db_offer.is_claimable = True
    payment = Payment(
        created=dt.datetime.now(dt.timezone.utc),
        type="revolut",
        offer_id=db_offer.id,
        amount=db_offer.reward,
        currency=db_offer.campaign.market.currency,
        destination="GB1234",
        successful=None,
    )
    db_session.add(payment)
    db_session.commit()
    # payment_processing gig in the right currency
    db_offer.campaign.market_slug = "us"
    db_offer.reward = USD_ALLOWED_BEFORE_1099 + 1
    assert db_influencer.remaining_usd_before_1099 == 0
    db_offer.reward = USD_ALLOWED_BEFORE_1099 - 100
    assert db_influencer.remaining_usd_before_1099 == 100


def test_influencer_remaining_usd_before_1099_offer_not_claimable(
    db_offer, db_influencer, db_session
):
    # submitted, but not payable gig in the right currency
    db_offer.is_claimable = False
    db_offer.campaign.market_slug = "us"
    db_offer.reward = USD_ALLOWED_BEFORE_1099 + 1
    db_offer.payable = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=12)
    assert db_influencer.remaining_usd_before_1099 == USD_ALLOWED_BEFORE_1099
    db_offer.reward = USD_ALLOWED_BEFORE_1099 - 100
    assert db_influencer.remaining_usd_before_1099 == USD_ALLOWED_BEFORE_1099


def test_influencer_remaining_usd_before_1099_offer_claimable(db_offer, db_influencer, db_session):
    # submitted gig, and payable now
    db_offer.is_claimable = True
    db_offer.campaign.market_slug = "us"
    db_offer.reward = USD_ALLOWED_BEFORE_1099 + 1
    db_offer.payable = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=12)
    assert db_influencer.remaining_usd_before_1099 == 0
    db_offer.reward = USD_ALLOWED_BEFORE_1099 - 100
    assert db_influencer.remaining_usd_before_1099 == 100
