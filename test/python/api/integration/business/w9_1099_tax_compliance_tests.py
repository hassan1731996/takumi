import datetime as dt

import pytest

from takumi.constants import USD_ALLOWED_BEFORE_1099
from takumi.models import Influencer, Offer
from takumi.models.market import us_market
from takumi.services import PaymentService
from takumi.services.payment import FailedPaymentPermissionException


def test_influencer_with_under_600_usd_income_and_no_w9_authorization_can_claim_payment(
    db_payable_offer: Offer,
):
    db_payable_offer.campaign.market_slug = us_market.slug
    db_payable_offer.reward = USD_ALLOWED_BEFORE_1099 - 1

    PaymentService.create(db_payable_offer.id, _get_payment_creation_data())


def test_influencer_with_over_600_usd_income_and_no_w9_authorization_cant_claim_payment(
    db_payable_offer: Offer,
):
    db_payable_offer.reward = USD_ALLOWED_BEFORE_1099
    db_payable_offer.campaign.market_slug = us_market.slug
    influencer: Influencer = db_payable_offer.influencer
    influencer.w9_tax_years_submitted = []

    with pytest.raises(
        FailedPaymentPermissionException,
        match=r"In order to claim this payment you need to fill out your W9",
    ):
        PaymentService.create(db_payable_offer.id, _get_payment_creation_data())


def test_influencer_with_over_600_usd_income_and_w9_authorization_can_claim_payment(
    db_payable_offer: Offer,
):
    db_payable_offer.reward = USD_ALLOWED_BEFORE_1099
    db_payable_offer.campaign.market_slug = us_market.slug
    influencer: Influencer = db_payable_offer.influencer
    influencer.w9_tax_years_submitted = [dt.datetime.now().year]

    PaymentService.create(db_payable_offer.id, _get_payment_creation_data())


def _get_payment_creation_data():
    return {"destination": {"type": "dwolla", "value": "test_destination"}}
