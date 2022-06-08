# encoding=utf-8

import mock
import pytest
from flask import url_for

from takumi.models.offer import STATES as OFFER_STATES


def _PAYOUT_PAYLOAD(country_code):
    return {
        "destination": {"type": "iban", "value": "{}1234".format(country_code)},
        "full_name": "Creator Mockerson",
        "bank_name": "Mockbank Ltd",
        "country_code": country_code,
    }


@pytest.mark.skip(reason="Deprecated view")
def test_offer_reject(offer, monkeypatch, influencer, influencer_client):
    monkeypatch.setattr("takumi.models.offer.Offer.can_reject", lambda *_: True)
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr("takumi.funds.AssetsFund.is_reservable", lambda *_: True)
    with mock.patch("takumi.services.offer.OfferService.get_by_id", return_value=offer):
        response = influencer_client.post(url_for("api.offer_reject", offer_id=offer.id))
    assert response.status_code == 200
    assert offer.state == OFFER_STATES.REJECTED


@pytest.mark.skip(reason="Deprecated view")
def test_offer_reserve(offer, monkeypatch, influencer, influencer_client):
    offer.campaign.state = "launched"
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr("takumi.funds.AssetsFund.is_reservable", lambda *_: True)
    monkeypatch.setattr("takumi.models.campaign.Campaign.is_fully_reserved", lambda *_: False)
    with mock.patch("takumi.services.offer.OfferService.get_by_id", return_value=offer):
        response = influencer_client.post(url_for("api.offer_reserve", offer_id=offer.id))
    assert response.status_code == 200
    assert offer.state == OFFER_STATES.ACCEPTED
