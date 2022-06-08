# encoding=utf-8

import datetime as dt

from freezegun import freeze_time

from takumi.models import InstagramPost

frozen_now = dt.datetime(2010, 1, 1, 0, 0, tzinfo=dt.timezone.utc)


def test_calculates_instagram_post_engagement():
    instagram_post = InstagramPost(likes=100, comments=10, followers=1000)
    assert instagram_post.engagement == 0.11


@freeze_time(frozen_now)
def test_is_stale():

    now = frozen_now
    hours = lambda h: dt.timedelta(hours=h)
    days = lambda d: dt.timedelta(days=d)

    assert not InstagramPost(posted=None, scraped=None).is_stale
    assert InstagramPost(posted=now, scraped=None).is_stale
    assert not InstagramPost(posted=now, scraped=now).is_stale
    assert InstagramPost(posted=now - hours(2), scraped=now - hours(2)).is_stale
    assert InstagramPost(posted=now - days(5), scraped=now - hours(25)).is_stale
    assert not InstagramPost(posted=now - days(5), scraped=now - hours(23)).is_stale
    assert InstagramPost(posted=now - days(31), scraped=now - days(8)).is_stale
    assert not InstagramPost(posted=now - days(31), scraped=now - days(6)).is_stale
