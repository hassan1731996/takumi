import datetime as dt
from typing import Optional

from tasktiger.exceptions import RetryException
from tasktiger.retry import fixed
from tasktiger.schedule import periodic

from core.facebook.instagram import InstagramObjectNotFound, InstagramUnknownError
from core.tasktiger import MAIN_QUEUE_NAME

from takumi.extensions import tiger
from takumi.models import StoryFrame

INSIGHT_QUEUE = f"{MAIN_QUEUE_NAME}.frame_insights"


@tiger.scheduled(periodic(minutes=15))
def fetch_expiring_insights() -> None:
    """Find stories that are about to expire and update the insights for them"""
    # Get frames posted between 23.5 and 24.25 hours ago
    range_start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24, minutes=15)
    range_end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=23, minutes=30)

    expiring_frames_q = StoryFrame.query.filter(
        StoryFrame.posted > range_start, StoryFrame.posted < range_end
    )

    for frame in expiring_frames_q:
        update_frame_insights.delay(frame.id)


@tiger.task(queue=INSIGHT_QUEUE, unique=True)
def update_frame_insights(story_frame_id: str) -> None:
    frame: Optional[StoryFrame] = StoryFrame.query.get(story_frame_id)
    if not frame:
        return

    try:
        frame.update_instagram_insights()
    except InstagramUnknownError:
        # Try again in 5 minutes
        raise RetryException(method=fixed(delay=300, max_retries=2))
    except InstagramObjectNotFound:
        return
