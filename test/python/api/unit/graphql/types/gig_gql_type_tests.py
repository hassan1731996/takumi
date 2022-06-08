import datetime as dt

import pytest

from takumi.gql.types.gig import Gig


@pytest.fixture(autouse=True, scope="function")
def monkey_all(monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.query.Query.all", lambda *args: [])


def test_gig_history_resolver_adds_reserve_event(gig, offer):
    offer.accepted = dt.datetime(2018, 1, 1)
    history = Gig.resolve_history(gig, "info")

    assert len(history) == 1
    assert history[0].type == "reserve"
    assert history[0].created == offer.accepted


def test_gig_history_resolver_adds_instagram_post_event(posted_gig, offer, instagram_post):
    offer.accepted = dt.datetime(2018, 1, 1, tzinfo=dt.timezone.utc)
    instagram_post.posted = dt.datetime(2018, 1, 2, tzinfo=dt.timezone.utc)
    history = Gig.resolve_history(posted_gig, "info")

    assert len(history) == 2
    assert history[0].type == "posted_to_instagram_feed"
    assert history[0].created == instagram_post.posted


@pytest.mark.skip()
def test_gig_history_resolver_adds_instagram_story_event(gig, offer, instagram_story):
    offer.accepted = dt.datetime(2018, 1, 1, tzinfo=dt.timezone.utc)
    instagram_story.story_frames[0].is_part_of_campaign = True
    instagram_story.story_frames[0].posted = dt.datetime(2018, 1, 2, tzinfo=dt.timezone.utc)
    gig.instagram_story = instagram_story
    history = Gig.resolve_history(gig, "info")

    assert len(history) == 2
    assert history[0].type == "posted_to_instagram_story"
    assert history[0].created == instagram_story.posted
