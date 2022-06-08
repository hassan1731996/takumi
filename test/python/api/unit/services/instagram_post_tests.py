import datetime as dt

import mock
import pytest
from mock import PropertyMock

from takumi.extensions import db
from takumi.services import InstagramPostService, OfferService


@pytest.fixture(autouse=True)
def disable_commits(monkeypatch):
    monkeypatch.setattr(db.session, "commit", lambda: None)
    yield


def test_create_sets_claimable_if_end_of_review_in_the_past(gig, monkeypatch):
    period = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    monkeypatch.setattr("takumi.services.gig.GigService.get_by_id", mock.Mock(return_value=gig))
    monkeypatch.setattr(
        "takumi.tasks.cdn.upload_instagram_post_media_to_cdn_and_update_instagram_post", mock.Mock()
    )

    with mock.patch(
        "takumi.models.gig.Gig.end_of_review_period", new_callable=PropertyMock, return_value=period
    ):
        with mock.patch("takumi.models.offer.Offer.has_all_gigs_claimable", return_value=True):
            with mock.patch.object(OfferService, "set_claimable") as mock_set_claimable:
                InstagramPostService.create(gig.id, "media_id")

    assert mock_set_claimable.called
