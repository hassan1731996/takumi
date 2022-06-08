import datetime as dt

import tasktiger
from sqlalchemy import and_, or_
from tasktiger.schedule import periodic

from core.tasktiger import MAIN_QUEUE_NAME

from takumi.extensions import tiger
from takumi.models import Gig, Post, Submission
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.post import PostTypes
from takumi.tasks.gig.link import link_gig

LINKING_QUEUE = f"{MAIN_QUEUE_NAME}.gig_link"


# Start time set to 00:15 in the past, meaning it'll run 15 minutes past each hour
@tiger.scheduled(periodic(hours=1, start_date=dt.datetime(2000, 1, 1, 0, 15)))
def gig_linker():
    """Go through unlinked gigs and check if the can be linked

    Find all gigs that have been approved but not linked.
    """

    # Only automatically search for gigs that have been approved in the last 48
    # hours. Any gigs posted after that have to be manually linked.
    two_days_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=48)

    gig_q = (
        Gig.query.join(Post)
        .join(Submission)
        .filter(
            Gig.state == GIG_STATES.APPROVED,
            Gig.instagram_post == None,  # noqa: E711
            Submission.caption != None,  # noqa: E711
            Post.post_type != PostTypes.story,  # noqa: E711
            or_(
                and_(
                    # Post doesn't have opened time, so just check approve date on gig
                    Post.opened == None,
                    Gig.approve_date > two_days_ago,
                ),
                and_(
                    # Post has opened, so we need to compare the Post.opened if approved was before
                    Post.opened < dt.datetime.now(dt.timezone.utc),
                    or_(
                        and_(Gig.approve_date > Post.opened, Gig.approve_date > two_days_ago),
                        and_(Gig.approve_date < Post.opened, Post.opened > two_days_ago),
                    ),
                ),
            ),
        )
    )

    total_count = gig_q.count() or 1
    # Spread out over 10 minutes, but no less than 5 seconds apart
    wait_time = max(int(600 / total_count), 5)

    interval = 0
    for gig in gig_q:
        tiger.tiger.delay(
            link_gig,
            args=[gig.id],
            queue=LINKING_QUEUE,
            retry_method=tasktiger.fixed(600, 5),  # Retry every 10 minutes, up to 5 times
            unique=True,
            when=dt.timedelta(seconds=interval),
        )
        interval += wait_time
