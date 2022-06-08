# encoding=utf-8

import datetime as dt

from freezegun import freeze_time

frozen_now = dt.datetime(2010, 1, 1, 0, 0, tzinfo=dt.timezone.utc)


@freeze_time(frozen_now)
def test_recent_gig_posted_returns_true_if_recent_instagram_post_was_posted(
    db_session, db_post, db_instagram_post
):
    # Arrange
    db_instagram_post.gig.post = db_post
    db_instagram_post.posted = frozen_now
    db_session.add(db_instagram_post)

    # Act & Assert
    assert db_post.recent_gig_posted() is True


def test_recent_gig_posted_returns_false_if_no_instagram_post_has_been_posted(
    db_session, db_post, db_gig
):
    # Arrange
    db_post.gigs = [db_gig]
    db_gig.instagram_post = None
    db_session.add_all([db_gig, db_post])

    # Act & Assert
    assert db_post.recent_gig_posted() is False


@freeze_time(frozen_now)
def test_recent_gig_posted_returns_false_if_recent_instagram_post_was_posted_later_than_the_cutoff(
    db_session, db_post, db_instagram_post
):
    # Arrange
    db_instagram_post.gig.post = db_post
    db_instagram_post.posted = frozen_now - dt.timedelta(days=8)
    db_session.add(db_instagram_post)

    # Act & Assert
    assert db_post.recent_gig_posted() is False
