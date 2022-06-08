import datetime as dt

import tasktiger
from tasktiger.schedule import periodic

from core.tasktiger import MAIN_QUEUE_NAME

from takumi.extensions import db, tiger
from takumi.models import Campaign, Influencer, InstagramPost, Offer
from takumi.tasks.influencer.update import update_influencer
from takumi.tasks.instagram_post import scrape_and_update_instagram_post_media

CAMPAIGN_MEDIA_QUEUE = f"{MAIN_QUEUE_NAME}.campaign_media"
INFLUENCER_UPDATE_QUEUE = f"{MAIN_QUEUE_NAME}.influencer_update"

get_now = lambda: dt.datetime.now(dt.timezone.utc)
get_week_ago = lambda: get_now() - dt.timedelta(days=7)
get_month_ago = lambda: get_now() - dt.timedelta(days=30)
get_quarter_ago = lambda: get_now() - dt.timedelta(days=90)

MAX_DELAY = 5  # seconds

#############################
# Update active influencers #
#############################


def schedule_influencer_update(update_seconds: int) -> None:
    q = (
        db.session.query(Influencer.id)
        .join(Offer)
        .join(Campaign)
        .filter(
            Campaign.state == Campaign.STATES.LAUNCHED,
            Offer.state.in_(
                [
                    Offer.STATES.ACCEPTED,
                    Offer.STATES.REQUESTED,
                    Offer.STATES.CANDIDATE,
                    Offer.STATES.APPROVED_BY_BRAND,
                ]
            ),
            ~Offer.is_claimable,
        )
        .distinct(Influencer.id)
    )

    step = min(update_seconds / q.count(), MAX_DELAY)
    delay = 0

    for (influencer_id,) in q:
        tiger.tiger.delay(
            update_influencer,
            args=[influencer_id],
            queue=INFLUENCER_UPDATE_QUEUE,
            retry_method=tasktiger.fixed(600, 5),  # Retry every 10 minutes, up to 5 times
            unique=True,
            when=dt.timedelta(seconds=delay),
        )
        delay += step


##########################
# Update Instagram Posts #
##########################


def schedule_media_updates(
    from_date: dt.datetime, to_date: dt.datetime, update_seconds: int
) -> None:
    """Find meida that needs updating and schedule updates

    Updates are spread over time to rate limit, with max MAX_DELAY seconds
    between the updates. The updates need to fit within update_seconds.

    For example, if you have 500 posts that need to be updated within 1000
    seconds, the updates will be scheduled 1000 / 500 = 2 seconds apart, but 10
    posts within 1000 seconds would be 1000 / 10 = 100 seconds apart. Using
    MAX_DELAY as the upper cap, means those 10 posts with be scheduled 5
    seconds apart.
    """
    q = db.session.query(InstagramPost.id).filter(
        InstagramPost.posted > from_date,
        InstagramPost.posted < to_date,
        InstagramPost.gig_id != None,
    )

    step = min(update_seconds / q.count(), MAX_DELAY)
    delay = 0

    for (ig_post_id,) in q:
        tiger.tiger.delay(
            scrape_and_update_instagram_post_media,
            args=[ig_post_id],
            queue=CAMPAIGN_MEDIA_QUEUE,
            retry_method=tasktiger.fixed(600, 5),  # Retry every 10 minutes, up to 5 times
            unique=True,
            when=dt.timedelta(seconds=delay),
        )
        delay += step


#############
# Schedules #
#############


@tiger.scheduled(periodic(hours=1))
def update_hourly() -> None:
    update_seconds = int(dt.timedelta(minutes=45).total_seconds())

    schedule_media_updates(
        from_date=get_week_ago(), to_date=get_now(), update_seconds=update_seconds
    )


@tiger.scheduled(
    periodic(hours=24, start_date=dt.datetime(2000, 1, 1, 2))
)  # Runs at 02:00 every morning
def update_daily() -> None:
    update_seconds = int(dt.timedelta(hours=8).total_seconds())

    schedule_media_updates(
        from_date=get_month_ago(), to_date=get_week_ago(), update_seconds=update_seconds
    )
    schedule_influencer_update(update_seconds)


@tiger.scheduled(
    periodic(hours=168, start_date=dt.datetime(2000, 1, 2, 6))
)  # Runs at 06:00 every sunday
def update_weekly() -> None:
    update_seconds = int(dt.timedelta(hours=18).total_seconds())

    schedule_media_updates(
        from_date=get_quarter_ago(), to_date=get_month_ago(), update_seconds=update_seconds
    )
