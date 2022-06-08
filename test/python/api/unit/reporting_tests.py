# encoding=utf-8

from decimal import Decimal

import mock

from takumi.reporting import _iter_gig_stats, get_posts_gigs_stats_csv


def get_mock_get_gig_posts_query(gig):
    return mock.patch(
        "takumi.reporting._get_gig_posts_query", lambda post: [(gig, Decimal("0.8000000000"))]
    )


def test_iter_gig_stats(posted_gig, post):
    posted_gig.instagram_post.sentiment = 0.2
    with get_mock_get_gig_posts_query(posted_gig):
        result = _iter_gig_stats([post])
        next(result)  # get past the post index row
        return_value = next(result)
    assert isinstance(return_value, dict)
    assert return_value["comment_sentiment"] == 0.8
    assert return_value["caption_sentiment"] == 0.2


def test_get_post_gig_stats_csv(post, posted_gig):
    with get_mock_get_gig_posts_query(posted_gig):
        with get_posts_gigs_stats_csv([post]) as data:
            assert data
            assert len(data.splitlines()) == 3
