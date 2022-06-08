import datetime as dt

import pytest

from takumi.gql.mutation.announcement import SeeAnnouncement
from takumi.gql.query import AnnouncementQuery
from takumi.gql.types.announcement import Announcement as AnnouncementGQLType
from takumi.models import Announcement


@pytest.mark.skip()
def test_announcements_query_only_returns_announcements_made_after_user_signed_up(
    client, db_session, db_influencer
):
    db_influencer.created = dt.datetime.now(dt.timezone.utc)

    # Announcement made before influencer signed up
    announcement1 = Announcement(title="title", message="message")
    announcement1.created = db_influencer.created - dt.timedelta(days=1)
    announcement1.active = True

    announcement2 = Announcement(title="title", message="message")
    announcement2.created = db_influencer.created + dt.timedelta(days=1)
    announcement2.active = True

    announcement3 = Announcement(title="title", message="message")
    announcement3.created = db_influencer.created + dt.timedelta(days=1)
    announcement3.active = True

    db_session.add_all([announcement1, announcement2, announcement3])
    db_session.commit()

    # Act
    with client.user_request_context(db_influencer.user):
        announcements = AnnouncementQuery().resolve_announcements("info").all()

    # Assert
    assert sorted([a.id for a in announcements]) == sorted([announcement2.id, announcement3.id])


def test_announcements_seeing_announcement_marks_it_as_seen(client, db_session, db_influencer):
    db_influencer.created = dt.datetime.now(dt.timezone.utc)

    announcement = Announcement(title="title", message="message")
    announcement.created = db_influencer.created + dt.timedelta(days=1)
    announcement.active = True
    db_session.add(announcement)
    db_session.commit()

    def _get_announcements():
        return AnnouncementQuery().resolve_announcements("info").all()

    def _has_seen_announcement(influencer, announcement):
        return AnnouncementGQLType.resolve_seen(announcement, "info")

    # Act
    with client.user_request_context(db_influencer.user):
        assert _get_announcements() == [announcement]
        assert not _has_seen_announcement(db_influencer, announcement)

        SeeAnnouncement().mutate("info", announcement.id)

        assert _get_announcements() == []
        assert _has_seen_announcement(db_influencer, announcement)
