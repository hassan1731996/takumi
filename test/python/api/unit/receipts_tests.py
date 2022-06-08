import datetime as dt

import mock

from takumi.models.offer import OfferEvent
from takumi.receipts import (
    _get_items_query,
    get_claimed_from_offer,
    get_influencer_receipt_items,
    get_influencer_receipt_pdf,
    get_totals_from_items,
)


def test_get_claimed_from_offer_with_payout_requested(offer, payment):
    assert get_claimed_from_offer(offer) is None
    payment.successful = True
    assert isinstance(get_claimed_from_offer(offer), dt.datetime)


@mock.patch("takumi.models.region.Region.get_tax_year_range")
def test_get_item_query_with_target_region_takes_regions_tax_year_into_account(
    mock_tax_year, influencer, region_city
):
    mock_tax_year.return_value = (dt.date.today(), dt.date.today())
    influencer.target_region = None
    _get_items_query(influencer, 2000)
    assert not mock_tax_year.called

    influencer.target_region = region_city
    _get_items_query(influencer, 2000)
    assert mock_tax_year.called


def test_get_influencer_receipt_items(influencer, offer):
    offer.payable = dt.datetime.now(dt.timezone.utc)
    offer.reward_per_post = 10000
    offer.get_event = lambda event: OfferEvent(
        type="payment_processing", created=dt.datetime.now(dt.timezone.utc)
    )
    with mock.patch("takumi.receipts._get_items_query") as m:
        m.return_value = [offer]
        items = get_influencer_receipt_items(influencer, 0)
        assert items
    currency, items = items.popitem()
    earned, claimed, brand, post, account = items[0]
    assert isinstance(earned, str)
    assert isinstance(claimed, str)
    assert isinstance(brand, str)
    assert isinstance(post, str)
    assert isinstance(account, float)


def test_get_totals_from_items():
    items = [("", "", "", "", 1), ("", "foo", "", "", 1)]
    assert get_totals_from_items(items) == (2, 1)
    items = [("", "foo", "", "", 1), ("", "foo", "", "", 1)]
    assert get_totals_from_items(items) == (2, 2)


def test_get_influencer_receipt_pdf(influencer, offer):
    offer.payable = dt.datetime.now(dt.timezone.utc)
    offer.get_event = lambda event: OfferEvent(
        type="payment_processing", created=dt.datetime.now(dt.timezone.utc)
    )
    offer.reward_per_post = 10000
    with mock.patch("takumi.receipts._get_items_query") as m:
        m.return_value = [offer]
        with mock.patch("takumi.receipts._call_service") as m:
            get_influencer_receipt_pdf(influencer, offer)
    assert m.called
