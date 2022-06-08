import requests
from sqlalchemy import func

from takumi.models import Offer

SERVICE_URL = "https://takumi-influencer-receipts-py3.herokuapp.com/receipts"


class ReceiptServiceException(Exception):
    pass


class MultipleCurrenciesException(Exception):
    pass


class NoReceiptsFoundException(Exception):
    pass


def _get_items_query(influencer, year):
    if influencer.target_region is None:
        query = Offer.query.filter(func.date_part("YEAR", Offer.payable) == year)
    else:
        start, end = influencer.target_region.get_tax_year_range(year)
        query = Offer.query.filter(
            func.date(Offer.payable) >= start, func.date(Offer.payable) <= end
        )
    return query.filter(Offer.influencer == influencer, Offer.is_claimable == True).order_by(
        Offer.payable
    )


def get_claimed_from_offer(offer):
    if offer.payment is not None and offer.payment.is_successful:
        return offer.payment.created


def get_influencer_receipt_items(influencer, year):
    """Return offer rows, grouped by currency"""
    result = {}
    for offer in _get_items_query(influencer, year):
        currency = offer.campaign.market.currency
        if currency not in result:
            result[currency] = []

        claimed = get_claimed_from_offer(offer)
        result[currency].append(
            (
                offer.payable.strftime("%d-%b-%y"),
                claimed and claimed.strftime("%d-%b-%y") or "",
                offer.campaign.advertiser.name,
                offer.campaign.name,
                float(offer.reward) / 100,
            )
        )

    return result


def _call_service(**kwargs):
    response = requests.post(SERVICE_URL, json=kwargs)
    try:
        response.raise_for_status()
    except requests.RequestException:
        raise ReceiptServiceException().with_traceback()
    return response


def get_totals_from_items(items):
    total, total_claimed = 0, 0
    for _, claimed, _, _, amount in items:
        total += amount
        if claimed:
            total_claimed += amount
    return total, total_claimed


def get_influencer_receipt_pdf(influencer, year, currency=None):
    """Generate PDF receipt for an influencer

    Currently only supports a single currency
    """
    items = get_influencer_receipt_items(influencer, year)
    if len(items) == 0:
        raise NoReceiptsFoundException()
    if len(items) > 1:
        if currency is None:
            raise MultipleCurrenciesException()
        elif currency not in items:
            raise NoReceiptsFoundException()
        items = {currency: items.get(currency)}

    # Pop the only currency the influencer had rewards in
    currency, items = items.popitem()

    # Escape underscores for latex
    username = influencer.username.replace("_", "\\_")

    total, total_claimed = get_totals_from_items(items)
    return _call_service(
        username=username,
        year=year,
        items=items,
        total=total,
        total_claimed=total_claimed,
        currency=currency,
    ).content
