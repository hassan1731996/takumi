import csv
import datetime as dt
from contextlib import contextmanager
from functools import lru_cache
from io import StringIO
from typing import Iterator, List, Optional, Union, cast

import sqlalchemy as sa
from dateutil.parser import parse as date_parse
from dateutil.relativedelta import relativedelta

from takumi.extensions import db
from takumi.models import Campaign, Gig, Offer

CAMPAIGN_COLUMNS = {
    "name": "Campaign name",
    "state": "Campaign state",
    "advertiser.name": "Client name",
    "opportunity_product_id": "Campaign tracking number",
    "created": "Live date",
    "FIRST_POST_DATE": "First post date",
    "DEADLINE": "Earliest deadline",
    "COMPLETION": "Campaign completion date",
    "reward_model": "Campaign type",
    "COUNTRY": "Location of campaign",
    "price": "Campaign price",
    "list_price": "Campaign list price",
    "market.currency": "Currency",
    "PLATFORMS": "Platform being used",
    "TOTAL_POSTS": "Total posted so far",
    "EXPECTED_POSTS": "Total expected",
}

OFFER_COLUMNS = {
    "influencer.username": "Username",
    "influencer.user.full_name": "Full name",
    "reward": "Reward",
    "PAYMENT": "Payment status",
}


MARKET_CURRENCY_MAP = {
    "uk": "GBP",
    "eu": "EUR",
    "us": "USD",
}


def get_campaigns_begun_in_month(month: str) -> List[Campaign]:
    """Return campaign that started in a given month

    A campaign is considered to have started in the month if the following is true:
        1. If the first live post happened in the month, if not live posts then;
        2. If the first paid gig was submitted for review in the month, if no paid gigs then;
        3. The campaign was created in the month
    """
    start_time = date_parse(f"{month}-01").replace(tzinfo=dt.timezone.utc)
    end_time = start_time + relativedelta(months=1)

    return Campaign.query.filter(
        Campaign.state.in_((Campaign.STATES.LAUNCHED, Campaign.STATES.COMPLETED)),
        Campaign.market_slug.in_(("eu", "uk", "us", "za")),
        sa.case(
            [
                (
                    Campaign.earliest_live_post_date != None,
                    sa.and_(
                        Campaign.earliest_live_post_date > start_time,  # type: ignore
                        Campaign.earliest_live_post_date < end_time,  # type: ignore
                    ),
                ),
                (
                    Campaign.earliest_submitted_and_claimed != None,
                    sa.and_(
                        Campaign.earliest_submitted_and_claimed > start_time,  # type: ignore
                        Campaign.earliest_submitted_and_claimed < end_time,  # type: ignore
                    ),
                ),
                (
                    sa.and_(
                        Campaign.earliest_live_post_date == None,
                        Campaign.earliest_submitted_and_claimed == None,
                    ),
                    sa.and_(
                        Campaign.created > start_time,
                        Campaign.created < end_time,
                    ),
                ),
            ],
            else_=False,
        ),
    ).all()


def get_headers() -> List[str]:
    return list(OFFER_COLUMNS.values()) + list(CAMPAIGN_COLUMNS.values())


def _default(prop: str, obj: Union[Campaign, Offer]) -> str:
    parts = prop.split(".")

    cell = getattr(obj, parts[0])
    for part in parts[1:]:
        cell = getattr(cell, part)

    return cell


def _get_completion(campaign: Campaign) -> Optional[dt.datetime]:
    if campaign.state == Campaign.STATES.COMPLETED:
        event = next((event for event in campaign.events[::-1] if event.type == "complete"), None)
        if event:
            return event.created
    return None


def _get_total_posts(campaign: Campaign) -> str:
    return str(
        db.session.query(sa.func.count(Gig.id))
        .join(Offer)
        .filter(
            Offer.campaign_id == campaign.id,
            Offer.state == Offer.STATES.ACCEPTED,
            Gig.is_posted,
        )
        .scalar()
    )


def _get_expected_posts(campaign: Campaign) -> str:
    accepted_offers = (
        db.session.query(sa.func.count(Offer.id))
        .filter(
            Offer.campaign_id == campaign.id,
            Offer.state == Offer.STATES.ACCEPTED,
        )
        .scalar()
    )
    post_count = len(campaign.posts)
    return str(accepted_offers * post_count)


@lru_cache
def _get_campaign_cells(campaign_id: str) -> List[str]:
    campaign: Campaign = Campaign.query.get(campaign_id)

    cells: List[str] = []

    for prop in CAMPAIGN_COLUMNS.keys():
        cell: Optional[Union[str, dt.datetime]]
        if prop == "FIRST_POST_DATE":
            cell = cast(
                dt.datetime,
                campaign.earliest_live_post_date or campaign.earliest_submitted_and_claimed or None,
            )
        elif prop == "DEADLINE":
            cell = min(post.deadline for post in campaign.posts)
        elif prop == "COMPLETION":
            cell = _get_completion(campaign)
        elif prop == "COUNTRY":
            cell = ",".join({region.country for region in campaign.targeting.regions})
        elif prop == "PLATFORMS":
            cell = ", ".join({post.post_type.title() for post in campaign.posts})
        elif prop == "TOTAL_POSTS":
            cell = _get_total_posts(campaign)
        elif prop == "EXPECTED_POSTS":
            cell = _get_expected_posts(campaign)
        else:
            cell = _default(prop, campaign)

        if cell is None:
            cell = ""
        if isinstance(cell, dt.datetime):
            cell = cell.strftime("%Y-%m-%d %H:%M:%S")
        if "price" in prop:
            cell = f"{int(cell) / 100:.02f}"

        cells.append(cell)
    return cells


def _get_payment_status(offer: Offer) -> str:
    if not offer.is_claimable:
        return "Not claimable"
    if offer.payment is None:
        return "Not claimed"

    return {None: "pending", True: "successful", False: "failed"}[offer.payment.successful]


def _get_offer_cells(offer: Offer) -> List[str]:
    cells: List[str] = []

    for prop in OFFER_COLUMNS.keys():
        if prop == "PAYMENT":
            cell = _get_payment_status(offer)
        else:
            cell = _default(prop, offer)

        if cell is None:
            cell = ""
        if isinstance(cell, dt.datetime):
            cell = cell.strftime("%Y-%m-%d %H:%M:%S")
        if "reward" in prop:
            cell = f"{int(cell) / 100:.02f}"

        cells.append(cell)

    return cells


def get_row(campaign: Campaign, offer: Offer) -> List[str]:
    offer_cells = _get_offer_cells(offer)
    campaign_cells = _get_campaign_cells(campaign.id)

    return offer_cells + campaign_cells


def get_rows(campaigns: List[Campaign]) -> Iterator[List[str]]:
    def _iter() -> Iterator[List[str]]:
        campaign: Campaign
        for campaign in campaigns:
            if campaign.targeting.regions and campaign.targeting.regions[0].name == "Takumiland":
                continue

            offer: Offer
            for offer in Offer.query.filter(
                Offer.campaign_id == campaign.id, Offer.state == Offer.STATES.ACCEPTED
            ):
                yield get_row(campaign, offer)

    return _iter()


@contextmanager
def get_campaign_month_report_csv(month: str) -> Iterator[str]:
    data = StringIO()
    writer = csv.writer(data, delimiter=";", quotechar="|", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(get_headers())

    campaigns = get_campaigns_begun_in_month(month)
    row_iter = get_rows(campaigns)
    for row in row_iter:
        writer.writerow(row)

    yield data.getvalue()

    data.close()
