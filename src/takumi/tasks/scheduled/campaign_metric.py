import datetime as dt

import tasktiger
from tasktiger.schedule import periodic

from core.tasktiger import MAIN_QUEUE_NAME

from takumi.extensions import db, tiger
from takumi.models.campaign import Campaign
from takumi.tasks.campaign import create_or_update_campaign_metric

MAX_DELAY = 3
CAMPAIGN_METRIC_QUEUE = f"{MAIN_QUEUE_NAME}.campaign_metric"


def schedule_campaign_metric_filling(update_seconds):
    """Get all campaigns ids and schedule updates.

    Args:
        update_seconds (Int): Update seconds.

    Note:
        Updates are spread over time to rate limit, with max MAX_DELAY seconds
        between the updates. The updates need to fit within update_seconds.
    """
    campaigns = db.session.query(Campaign.id)

    step = min(update_seconds / campaigns.count(), MAX_DELAY)
    delay = 0

    for (campaign_id,) in campaigns:
        tiger.tiger.delay(
            create_or_update_campaign_metric,
            args=[campaign_id],
            queue=CAMPAIGN_METRIC_QUEUE,
            retry_method=tasktiger.fixed(600, 5),
            unique=True,
            when=dt.timedelta(seconds=delay),
        )
        delay += step


@tiger.scheduled(periodic(hours=24))
def update_daily():
    """Scheduled function that runs daily."""
    update_seconds = int(dt.timedelta(minutes=1).total_seconds())

    schedule_campaign_metric_filling(update_seconds)
