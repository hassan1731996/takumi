import datetime as dt
from collections import namedtuple

import mock

from takumi.search.influencer import InfluencerSearch
from takumi.slack import (
    brand_reported_gig,
    gig_submit,
    influencer_report,
    influencer_untagged,
    new_influencer,
    offer_reserve,
    payout_failure_dwolla,
)
from takumi.slack.channels.influencers import _get_influencer_untagged_count_by_region
from takumi.slack.models import GigAttachment, InfluencerAttachment, UntaggedAttachment
from takumi.slack.utils import only_in_production


def test_only_in_production_decorator():
    mock_check = mock.Mock()

    @only_in_production
    def func():
        mock_check()

    with mock.patch("takumi.slack.utils.current_app") as mock_app:
        mock_app.config = {"RELEASE_STAGE": "development"}
        func()

    assert not mock_check.called

    with mock.patch("takumi.slack.utils.current_app") as mock_app:
        mock_app.config = {"RELEASE_STAGE": "production"}
        func()

    assert mock_check.called


def test_new_influencer_notification(influencer, slack_post):
    with mock.patch("takumi.slack.utils.current_app") as mock_app:
        mock_app.config = {"RELEASE_STAGE": "production", "WEBAPP_URL": "http://"}
        new_influencer(influencer)
    assert slack_post.call_count == 1


def test_gig_submit(gig, submission, slack_post):
    with mock.patch("sqlalchemy.orm.query.Query.count", return_value=1):
        gig.submission.caption = "Post caption #yolo"

        with mock.patch("takumi.slack.utils.current_app") as mock_app:
            mock_app.config = {"RELEASE_STAGE": "production", "WEBAPP_URL": "http://"}
            gig_submit(gig)

    published_caption = slack_post.call_args_list[0][1]["attachments"][0]["text"]
    assert published_caption[1:-1] == "Post caption #yolo"


def test_offer_reserve(offer, slack_post):
    with mock.patch("sqlalchemy.orm.query.Query.count", return_value=0):
        with mock.patch("takumi.slack.utils.current_app") as mock_app:
            mock_app.config = {"RELEASE_STAGE": "production", "WEBAPP_URL": "http://"}
            offer_reserve(offer)
    assert slack_post.call_count == 1


def test_payout_failure_dwolla(payment, slack_post, monkeypatch):
    monkeypatch.setattr(
        "takumi.slack.channels.monitoring.get_influencer_attachment", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(
        "takumi.slack.channels.monitoring.get_campaign_attachment", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(
        "takumi.slack.channels.monitoring.get_payment_attachment", lambda *args, **kwargs: {}
    )
    failure = namedtuple("TransferFailure", ["code", "description"])(
        code="R001", description="mock fail payout"
    )
    payout_failure_dwolla(payment, failure)

    assert slack_post.call_count == 1


def test_influencer_untagged_count_by_region_returns_untagged_attachment(region):
    with mock.patch("core.elasticsearch.ResultSet.count") as m:
        m.return_value = 10
        result = _get_influencer_untagged_count_by_region(InfluencerSearch(), region)
        assert "10" in result["value"]
        assert region.name in result["title"]


def test_influencer_untagged_count_by_region_returns_none_if_count_lt_1(region):
    with mock.patch("core.elasticsearch.ResultSet.count") as m:
        m.return_value = 0
        assert _get_influencer_untagged_count_by_region(InfluencerSearch(), region) is None


def test_influencer_untagged(influencer_user, slack_post):
    influencer_1 = mock.Mock(
        followers=1000,
        username="user_1",
        user_created=dt.datetime.now(dt.timezone.utc).isoformat(),
        user=influencer_user,
    )
    influencer_2 = mock.Mock(
        followers=1000,
        username="user_2",
        user_created=dt.datetime.now(dt.timezone.utc).isoformat(),
        user=influencer_user,
    )
    with mock.patch("sqlalchemy.orm.query.Query.__iter__", return_value=iter([])):
        with mock.patch(
            "core.elasticsearch.ResultSet.__getitem__", side_effect=[influencer_1, influencer_2]
        ):
            with mock.patch("core.elasticsearch.ResultSet.count", return_value=2):
                influencer_untagged()
                slack_post.assert_called()


@mock.patch("takumi.search.influencer.InfluencerSearch.execute")
def test_influencer_untagged_returns_early_if_no_total_untagged(mock_get_untagged_signups, app):
    mock_get_untagged_signups.return_value.count.return_value = 0
    assert influencer_untagged() is None


def test_influencer_report(client):
    with mock.patch("sqlalchemy.orm.query.Query.count") as m:
        m.return_value = 2
        with mock.patch("core.elasticsearch.ResultSet.count") as m:
            m.return_value = 2
            influencer_report()


def test_influencer_attachment_render_returns_attachment_with_influencer_info(influencer):
    rendered = InfluencerAttachment(influencer).render()

    assert influencer.username in rendered["title"]
    assert influencer.id in rendered["title_link"]


def test_untagged_attachment_render_returns_attachment_with_untagged_info():
    rendered = UntaggedAttachment("mockregion", 10).render()
    assert "mockregion" in rendered["title"]
    assert "10" in rendered["value"]


def test_gig_attachment_render_submitted_returns_info_about_gig_submission(gig, submission):
    gig.submission.caption = "caption"
    rendered = GigAttachment(gig).render_submitted()

    assert "Submitted a photo for review in" in rendered["title"]
    assert "caption" in rendered["text"]


def test_gig_attachment_render_posted_story_returns_info_about_gig_submission(gig, submission):
    rendered = GigAttachment(gig).render_posted_story()

    assert "Posted a story for review in" in rendered["title"]
    assert "Head over to admin to choose story frames" in rendered["text"]


def test_brand_reported_gig_formats_information_correctly(gig, advertiser, advertiser_user):
    with mock.patch("takumi.slack.channels.brand_reports.SlackClient") as mock_client:
        brand_reported_gig(gig, advertiser, "reason", advertiser_user)

    kwargs = mock_client.return_value.post_message.call_args[1]

    assert kwargs["channel"] == "brand-reports"
    assert (
        kwargs["text"] == f"A client has just reported a gig from {gig.offer.influencer.username}"
    )

    assert kwargs["attachments"][0]["title"] == advertiser_user.full_name
    assert kwargs["attachments"][1]["title"] == advertiser_user.email
    assert kwargs["attachments"][2]["title"] == advertiser.name
    assert kwargs["attachments"][3]["title"] == gig.offer.campaign.name
    assert kwargs["attachments"][4]["title"] == gig.offer.influencer.username
    assert kwargs["attachments"][5]["title"] == "Client Report"
    assert kwargs["attachments"][5]["text"] == "reason"
