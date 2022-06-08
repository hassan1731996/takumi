import mock
from flask import url_for

from takumi.receipts import ReceiptServiceException


def test_get_statement(influencer_client, influencer, gig):
    with mock.patch("takumi.views.statements.get_influencer_receipt_pdf") as m:
        m.return_value = ""
        assert influencer_client.get(url_for("api.get_statement", year=0)).status_code == 200


def test_get_statement_http_error_raises_receipt_service_exception(
    influencer_client, influencer, gig
):
    with mock.patch("takumi.views.statements.get_influencer_receipt_pdf") as m:
        m.side_effect = ReceiptServiceException()
        assert influencer_client.get(url_for("api.get_statement", year=0)).status_code == 503
