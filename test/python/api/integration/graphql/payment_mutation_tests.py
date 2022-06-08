import mock

from takumi.constants import PAYOUT_LIMITS
from takumi.gql.mutation.finance import ApprovePayment
from takumi.gql.mutation.payment import RequestPayment
from takumi.models import Payment


def test_requesting_payment_auto_approve(client, db_offer, db_influencer_user, db_session):
    db_offer.is_claimable = True
    db_session.commit()

    with client.user_request_context(db_influencer_user):
        response = RequestPayment().mutate(
            "info", offer_id=db_offer.id, destination_type="takumi", destination_value="test"
        )

    assert response.ok
    assert db_offer.payment is not None
    assert db_offer.payment.approved


def test_requesting_payment_require_approval(client, db_offer, db_influencer_user, db_session):
    db_offer.reward = PAYOUT_LIMITS[db_offer.campaign.market.currency] + 1
    db_offer.is_claimable = True
    db_session.commit()

    with mock.patch("takumi.services.payment.slack") as mock_slack:
        with client.user_request_context(db_influencer_user):
            response = RequestPayment().mutate(
                "info", offer_id=db_offer.id, destination_type="takumi", destination_value="test"
            )

    assert response.ok
    assert db_offer.payment is not None
    assert not db_offer.payment.approved

    mock_slack.payment_needs_approval.assert_called_with(db_offer.payment)


def test_approve_payment(client, db_session, db_developer_user, payment_factory):
    payment = payment_factory(state=Payment.STATES.PENDING, approved=False)

    db_session.add(payment)
    db_session.commit()

    with client.user_request_context(db_developer_user):
        response = ApprovePayment().mutate("info", payment_id=payment.id)

        assert response.ok is True
        assert response.payment == payment
        assert response.payment.approved is True
