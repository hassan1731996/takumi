from takumi.gql.query.finance import FinanceQuery
from takumi.models import Payment


def test_qraphql_query_unapproved_payments(client, db_session, db_developer_user, payment_factory):
    pending_approved = payment_factory(state=Payment.STATES.PENDING, approved=True)
    pending_not_approved = payment_factory(state=Payment.STATES.PENDING, approved=False)
    requested_approved = payment_factory(state=Payment.STATES.REQUESTED, approved=False)
    requested_not_approved = payment_factory(state=Payment.STATES.REQUESTED, approved=False)

    db_session.add(pending_approved)
    db_session.add(pending_not_approved)
    db_session.add(requested_approved)
    db_session.add(requested_not_approved)
    db_session.commit()

    with client.user_request_context(db_developer_user):
        result = FinanceQuery().resolve_unapproved_payments("info").all()

        assert len(result) == 1
        assert result[0] == pending_not_approved.offer
