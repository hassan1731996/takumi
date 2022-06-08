import mock
import pytest

from takumi.services import GigService
from takumi.services.exceptions import GigInvalidCaptionException, GigUpdateCaptionException


def test_gig_create_submission_sets_order(gig):
    gig.state = "requires_resubmit"
    media = [
        {"type": "image", "url": "http://first.jpg"},
        {"type": "image", "url": "http://second.jpg"},
        {"type": "image", "url": "http://third.jpg"},
    ]

    GigService(gig).create_submission("caption", media)

    assert gig.submission.media[0].order == 0
    assert gig.submission.media[0].url == "http://first.jpg"
    assert gig.submission.media[1].order == 1
    assert gig.submission.media[1].url == "http://second.jpg"
    assert gig.submission.media[2].order == 2
    assert gig.submission.media[2].url == "http://third.jpg"


def test_update_latest_submission_caption_raises_if_no_submission(gig):
    assert gig.submission is None

    with pytest.raises(GigUpdateCaptionException, match="Gig has no submission"):
        GigService(gig).update_latest_submission_caption("new caption")


def test_update_latest_submission_caption_raises_if_already_posted(gig, submission):
    gig.is_verified = True

    with pytest.raises(GigUpdateCaptionException, match="Gig has already been posted"):
        GigService(gig).update_latest_submission_caption("new caption")


def test_update_latest_submission_caption_validates_caption(gig, submission, post):
    post.conditions = [{"type": "hashtag", "value": "ad"}]

    with pytest.raises(GigInvalidCaptionException, match="Missing hashtag: #ad"):
        GigService(gig).update_latest_submission_caption("I promise this isn't an ad guys")


def test_update_latest_submission_caption_updates_the_caption(gig, submission):
    GigService(gig).update_latest_submission_caption("A completely new caption")

    assert submission.caption == "A completely new caption"


def test_gig_mark_as_posted(app, gig):
    gig.is_posted = False

    GigService(gig).mark_as_posted(True)

    assert gig.is_posted == True

    GigService(gig).mark_as_posted(False)

    assert gig.is_posted == False


def test_gig_mark_as_verified(app, gig):
    gig.is_verified = False

    GigService(gig).mark_as_verified(True)

    assert gig.is_verified == True

    GigService(gig).mark_as_verified(False)

    assert gig.is_verified == False


def test_report_gig_notifies_brand_report_slack_for_advertisers(posted_gig, advertiser_user):
    with mock.patch("takumi.services.gig.slack") as mock_slack:
        GigService(posted_gig).report_gig("reason", reporter=advertiser_user)

    assert mock_slack.brand_reported_gig.called
    assert not mock_slack.gig_reported.called


def test_report_gig_notifies_normally_for_non_brand_user(posted_gig, campaign_manager):
    with mock.patch("takumi.services.gig.slack") as mock_slack:
        GigService(posted_gig).report_gig("reason", reporter=campaign_manager)

    assert not mock_slack.brand_reported_gig.called
    assert mock_slack.gig_reported.called


def test_report_gig_notifies_normally_for_no_user(posted_gig):
    with mock.patch("takumi.services.gig.slack") as mock_slack:
        GigService(posted_gig).report_gig("reason", reporter=None)  # System reporting

    assert not mock_slack.brand_reported_gig.called
    assert mock_slack.gig_reported.called


def test_request_resubmission_unsets_posted_if_set(posted_gig):
    service = GigService(posted_gig)
    service.mark_as_verified(True)

    assert posted_gig.is_posted is True
    assert posted_gig.is_verified is True

    service.report_gig("reason")
    service.request_resubmission("reason", "explanation")

    assert posted_gig.is_posted is False
    assert posted_gig.is_verified is False
