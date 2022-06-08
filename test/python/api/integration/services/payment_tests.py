import datetime as dt
import json

import mock
import pytest

from takumi.constants import USD_ALLOWED_BEFORE_1099
from takumi.models import Offer
from takumi.models.market import eu_market, uk_market, us_market
from takumi.models.payment import STATES
from takumi.models.payment_authorization import PaymentAuthorization
from takumi.payments.authorization_checkers import USAHasReturnedW9FormChecker
from takumi.payments.permissions import USATaxInfoPermission
from takumi.services.payment import (
    FailedPaymentMethodException,
    FailedPaymentPermissionException,
    OfferAlreadyPaidException,
    OfferNotClaimableException,
    OfferNotFoundException,
    PaymentGatewayException,
    PaymentRequestFailedException,
    PaymentService,
    PendingPaymentExistsException,
)
from takumi.utils import uuid4_str


def test_payment_service_get_by_id(db_payment):
    payment = PaymentService.get_by_id(db_payment.id)
    assert payment == db_payment


def test_payment_service_create_fails_when_offer_not_found(db_session):
    # Arrange
    offer_id = uuid4_str()

    # Act & Assert
    with pytest.raises(OfferNotFoundException):
        PaymentService.create(offer_id, {})


def test_payment_service_create_fails_when_offer_not_claimable(db_offer):
    # Arrange
    db_offer.is_claimable = False

    # Act & Assert
    with pytest.raises(OfferNotClaimableException):
        PaymentService.create(db_offer.id, {})


def test_payment_service_create_success(db_offer):
    # Arrange
    db_offer.is_claimable = True
    data = _get_payment_data_skeleton()
    data["destination"]["value"] = "GBxxxxxx"

    # Act
    payment = PaymentService.create(db_offer.id, data)

    # Assert
    assert payment.type == "revolut"
    assert payment.amount == db_offer.reward
    assert payment.currency == db_offer.campaign.market.currency
    assert payment.destination == "GBxxxxxx"
    assert payment.state == STATES.PENDING
    assert payment.details == data
    assert payment.offer == db_offer
    assert payment.successful is None
    assert db_offer.claimed == payment.created


def test_payment_service_create_fails_if_pending_payment_exists(db_offer):
    # Arrange
    db_offer.is_claimable = True
    data = _get_payment_data_skeleton()
    data["destination"]["value"] = "GBxxxxxx"

    # Act & Assert
    PaymentService.create(db_offer.id, data)
    with pytest.raises(PendingPaymentExistsException):
        PaymentService.create(db_offer.id, data)


def test_payment_service_create_fails_if_paid_payment_exists(db_offer):
    # Arrange
    db_offer.is_claimable = True
    data = _get_payment_data_skeleton()
    data["destination"]["value"] = "GBxxxxxx"

    payment = PaymentService.create(db_offer.id, data)
    payment.successful = True

    # Act & Assert
    assert payment.is_successful
    assert db_offer.is_paid
    with pytest.raises(OfferAlreadyPaidException):
        PaymentService.create(db_offer.id, data)


def test_payment_service_create_fails_permission_check_for_tax_info(db_offer: Offer):
    db_offer.is_claimable = True
    db_offer.campaign.market_slug = us_market.slug
    db_offer.payable = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=12)

    db_offer.reward = USD_ALLOWED_BEFORE_1099 + 1

    with pytest.raises(FailedPaymentPermissionException, match=USATaxInfoPermission.fail_message):
        PaymentService.create(db_offer.id, _get_payment_data_skeleton())


def test_payment_service_create_passes_permission_check_for_tax_info_with_w9_auth(
    db_session, db_offer
):
    # Arrange
    db_offer.is_claimable = True
    db_offer.campaign.market_slug = us_market.slug
    db_offer.payable = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=12)

    authorize_tax = PaymentAuthorization(
        slug=USAHasReturnedW9FormChecker.slug, influencer_id=db_offer.influencer_id
    )
    db_session.add(authorize_tax)
    db_session.commit()
    payment_data = _get_payment_data_skeleton()
    payment_data["destination"]["type"] = "dwolla"

    db_offer.reward = USD_ALLOWED_BEFORE_1099 + 1

    # Act
    PaymentService.create(db_offer.id, payment_data)


def test_payment_service_create_fails_payment_method_check_for_usd_payment_to_iban(db_offer):
    # Arrange
    db_offer.is_claimable = True
    db_offer.campaign.market_slug = us_market.slug
    db_offer.payable = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=12)

    # Act
    with pytest.raises(FailedPaymentMethodException) as exc:
        PaymentService.create(db_offer.id, _get_payment_data_skeleton())

    assert "Currency USD not supported for payment method revolut" in exc.exconly()


def test_payment_service_create_fails_payment_method_check_for_non_usd_payment_to_dwolla(db_offer):
    # Arrange
    db_offer.is_claimable = True
    db_offer.campaign.market_slug = eu_market.slug
    db_offer.payable = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=12)
    payment_data = _get_payment_data_skeleton()
    payment_data["destination"]["type"] = "dwolla"

    # Act
    with pytest.raises(FailedPaymentMethodException) as exc:
        PaymentService.create(db_offer.id, payment_data)

    assert "Currency EUR not supported for payment method dwolla" in exc.exconly()


def test_payment_service_create_success_for_gbp_payment_to_gb_iban(db_offer):
    # Arrange
    db_offer.is_claimable = True
    db_offer.payable = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=12)
    db_offer.campaign.market_slug = uk_market.slug
    payment_data = _get_payment_data_skeleton()
    payment_data["destination"]["value"] = "GBxxxx"

    # Act
    PaymentService.create(db_offer.id, payment_data)


def test_payment_service_create_success_for_eur_payment_to_non_gb_iban(db_offer):
    # Arrange
    db_offer.is_claimable = True
    db_offer.payable = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=12)
    db_offer.campaign.market_slug = eu_market.slug
    payment_data = _get_payment_data_skeleton()
    payment_data["destination"]["value"] = "derp"

    # Act
    PaymentService.create(db_offer.id, payment_data)


def test_payment_service_request_fails_on_payout(monkeypatch, db_payment):
    # Arrange
    monkeypatch.setattr("takumi.services.payment.slack.payout_request_failure", lambda *args: None)
    monkeypatch.setattr("takumi.services.payment.capture_exception", lambda *args: None)
    monkeypatch.setattr(
        "takumi.services.payment.logic.PaymentServiceProvider.payout",
        mock.Mock(side_effect=PaymentGatewayException),
    )

    data = _get_payment_data_skeleton()

    # Act & Assert
    with pytest.raises(PaymentRequestFailedException):
        with PaymentService(db_payment) as service:
            service.request(data)


def test_payment_service_request_success(monkeypatch, db_payment):
    # Arrange
    monkeypatch.setattr(
        "takumi.services.payment.logic.PaymentServiceProvider.payout",
        lambda *args, **kwargs: ("pspReference", "raw_response"),
    )

    data = _get_payment_data_skeleton()

    # Act
    with PaymentService(db_payment) as service:
        service.request(data)

    # Assert
    assert db_payment.reference == "pspReference"
    assert db_payment.state == STATES.REQUESTED


def test_payment_service_request_failed_success(db_payment):
    assert db_payment.state != STATES.FAILED
    assert db_payment.destination != None
    db_payment.details = {"info": "foo"}

    with PaymentService(db_payment) as service:
        service.request_failed("reason")

    assert db_payment.state == STATES.FAILED
    assert db_payment.details == {}
    assert db_payment.destination == None


def test_payment_service_doesnt_store_payment_details_in_events(monkeypatch, db_offer):
    monkeypatch.setattr(
        "takumi.services.payment.logic.PaymentServiceProvider.payout",
        lambda *args, **kwargs: ("pspReference", "raw_response"),
    )

    db_offer.is_claimable = True
    iban = "GBSENSITIVE"

    data = _get_payment_data_skeleton()
    data["destination"]["value"] = iban

    payment = PaymentService.create(db_offer.id, data)

    assert payment.details == data

    with PaymentService(payment) as service:
        service.check_for_approval()

    assert payment.approved

    with PaymentService(payment) as service:
        service.request(data)

    assert payment.details == {}
    assert payment.destination == None

    for event in payment.events:
        assert iban not in json.dumps(event)


#############################################
# Utility functions for tests defined below #
#############################################
def _get_payment_data_skeleton():
    return {
        "full_name": "test_name",
        "bank_name": "test_bank",
        "country_code": "uk",
        "destination": {"type": "revolut", "value": "b08968b5-635a-443b-bebc-55486ba0414f"},
    }
