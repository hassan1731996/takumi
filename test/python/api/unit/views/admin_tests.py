# encoding=utf-8
import mock
from flask import url_for

from takumi.utils import uuid4_str


def test_get_campaign_media_urls_returns_404_if_campaign_not_found(monkeypatch, client):
    # Arrange
    monkeypatch.setattr(
        "takumi.views.admin.campaigns.CampaignService.get_by_report_token",
        mock.Mock(return_value=None),
    )

    # Act
    response = client.get(url_for("api.get_campaign_post_urls", report_token=uuid4_str()))

    # Assert
    assert response.status_code == 404
    assert response.json["error"] == "Campaign not found"


def test_get_campaign_media_urls_returns_media_urls(monkeypatch, campaign, instagram_post, client):
    # Arrange
    instagram_post.media[0].url = "some_url"
    monkeypatch.setattr(
        "takumi.views.admin.campaigns.CampaignService.get_by_report_token",
        mock.Mock(return_value=campaign),
    )
    monkeypatch.setattr(
        "takumi.views.admin.campaigns.InstagramPostService.get_instagram_posts_from_post",
        mock.Mock(return_value=[instagram_post]),
    )

    # Act
    response = client.get(url_for("api.get_campaign_post_urls", report_token=campaign.report_token))

    # Assert
    assert response.status_code == 200
    assert response.json == {
        campaign.name: {"Post 1": {instagram_post.gig.offer.influencer.username: ["some_url"]}}
    }


def test_get_campaign_media_urls_for_stories_returns_media_urls(
    monkeypatch, campaign, instagram_story, client
):
    # Arrange
    instagram_story.story_frames[0].media.url = "some_url"
    monkeypatch.setattr(
        "takumi.views.admin.campaigns.CampaignService.get_by_report_token",
        mock.Mock(return_value=campaign),
    )
    monkeypatch.setattr(
        "takumi.views.admin.campaigns.InstagramStoryService.get_instagram_stories_from_post",
        mock.Mock(return_value=[instagram_story]),
    )

    # Act
    response = client.get(url_for("api.get_campaign_post_urls", report_token=campaign.report_token))

    # Assert
    assert response.status_code == 200
    assert response.json == {
        campaign.name: {"Post 1": {instagram_story.gig.offer.influencer.username: ["some_url"]}}
    }


def test_get_campaign_media_urls_normalizes_campaign_names(monkeypatch, campaign, client):
    # Arrange
    campaign.name = "Honest Bio Tee - Das biozertifizierte Teegetränk aus den USA"
    monkeypatch.setattr(
        "takumi.views.admin.campaigns.CampaignService.get_by_report_token",
        mock.Mock(return_value=campaign),
    )
    monkeypatch.setattr(
        "takumi.views.admin.campaigns.InstagramPostService.get_instagram_posts_from_post",
        mock.Mock(return_value=[]),
    )

    # Act
    response = client.get(url_for("api.get_campaign_post_urls", report_token=campaign.report_token))

    # Assert
    assert response.status_code == 200
    assert "Honest Bio Tee - Das biozertifizierte Teegetrank aus den USA" in response.json


def test_get_gig_media_urls_returns_404_if_gig_not_found(monkeypatch, client):
    # Arrange
    monkeypatch.setattr(
        "takumi.views.admin.gigs.GigService.get_by_id", mock.Mock(return_value=None)
    )

    # Act
    response = client.post(
        url_for("api.get_gig_media_urls", gig_id=uuid4_str()), data={"report_token": uuid4_str()}
    )

    # Assert
    assert response.status_code == 404
    assert response.json["error"] == "Gig not found"


def test_get_gig_media_urls_returns_404_if_campaign_not_found(monkeypatch, gig, client):
    # Arrange
    monkeypatch.setattr("takumi.views.admin.gigs.GigService.get_by_id", mock.Mock(return_value=gig))
    monkeypatch.setattr(
        "takumi.views.admin.campaigns.CampaignService.get_by_report_token",
        mock.Mock(return_value=None),
    )

    # Act
    response = client.post(
        url_for("api.get_gig_media_urls", gig_id=gig.id), data={"report_token": uuid4_str()}
    )

    # Assert
    assert response.status_code == 404
    assert response.json["error"] == "Campaign not found"


def test_get_gig_media_urls_returns_media_urls(
    monkeypatch, posted_gig, campaign, instagram_post, client
):
    # Arrange
    instagram_post.media[0].url = "some_url"
    monkeypatch.setattr(
        "takumi.views.admin.gigs.GigService.get_by_id", mock.Mock(return_value=posted_gig)
    )
    monkeypatch.setattr(
        "takumi.views.admin.campaigns.CampaignService.get_by_report_token",
        mock.Mock(return_value=campaign),
    )
    monkeypatch.setattr(
        "takumi.views.admin.campaigns.InstagramPostService.get_instagram_posts_from_post",
        mock.Mock(return_value=[instagram_post]),
    )

    # Act
    response = client.post(
        url_for("api.get_gig_media_urls", gig_id=posted_gig.id), data={"report_token": uuid4_str()}
    )

    # Assert
    assert response.status_code == 200
    assert response.json == {posted_gig.offer.influencer.username: ["some_url"]}


def test_get_gig_media_urls_returns_empty_media_urls(
    monkeypatch, gig, campaign, instagram_post, client
):
    # Arrange
    instagram_post.media[0].url = "some_url"
    monkeypatch.setattr("takumi.views.admin.gigs.GigService.get_by_id", mock.Mock(return_value=gig))
    monkeypatch.setattr(
        "takumi.views.admin.campaigns.CampaignService.get_by_report_token",
        mock.Mock(return_value=campaign),
    )
    monkeypatch.setattr(
        "takumi.views.admin.campaigns.InstagramPostService.get_instagram_posts_from_post",
        mock.Mock(return_value=[instagram_post]),
    )

    # Act
    response = client.post(
        url_for("api.get_gig_media_urls", gig_id=gig.id), data={"report_token": uuid4_str()}
    )

    # Assert
    assert response.status_code == 200
    assert response.json == {gig.offer.influencer.username: []}
