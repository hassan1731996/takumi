# encoding=utf-8
import datetime as dt

import mock

from takumi.constants import NEW_EXTENDED_CLAIM_HOURS_DATE
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.insight import STATES as INSIGHT_STATES


def test_is_claimable_returns_true_if_gig_is_rejected(monkeypatch, gig):
    # Arrange
    assert gig.is_claimable is False
    gig.state = GIG_STATES.REJECTED

    # Act
    result = gig.is_claimable

    # Assert
    assert result is True


def test_is_claimable_returns_true_if_it_is_live_and_passed_claimable_time(monkeypatch, gig):
    # Arrange
    monkeypatch.setattr("takumi.models.gig.Gig.is_live", mock.PropertyMock(return_value=True))
    monkeypatch.setattr(
        "takumi.models.gig.Gig.is_passed_claimable_time", mock.PropertyMock(return_value=True)
    )

    # Act
    result = gig.is_claimable

    # Assert
    assert result is True


def test_is_claimable_returns_false_if_it_is_live_and_not_passed_claimable_time(monkeypatch, gig):
    # Arrange
    monkeypatch.setattr("takumi.models.gig.Gig.is_live", mock.PropertyMock(return_value=True))
    monkeypatch.setattr(
        "takumi.models.gig.Gig.is_passed_claimable_time", mock.PropertyMock(return_value=False)
    )

    # Act
    result = gig.is_claimable

    # Assert
    assert result is False


def test_is_claimable_returns_false_if_it_is_not_live_and_passed_claimable_time(monkeypatch, gig):
    # Arrange
    monkeypatch.setattr("takumi.models.gig.Gig.is_live", mock.PropertyMock(return_value=False))
    monkeypatch.setattr(
        "takumi.models.gig.Gig.is_passed_claimable_time", mock.PropertyMock(return_value=True)
    )

    # Act
    result = gig.is_claimable

    # Assert
    assert result is False


def test_is_claimable_is_false_if_missing_insight_when_required(monkeypatch, campaign, gig):
    campaign.require_insights = True

    monkeypatch.setattr("takumi.models.gig.Gig.is_live", mock.PropertyMock(return_value=True))
    monkeypatch.setattr(
        "takumi.models.gig.Gig.is_passed_claimable_time", mock.PropertyMock(return_value=True)
    )

    assert gig.insight is None
    assert gig.is_missing_insights is True
    assert gig.is_claimable is False


def test_is_claimable_is_true_with_insight_when_required(monkeypatch, campaign, gig, post_insight):
    campaign.require_insights = True
    post_insight.state = INSIGHT_STATES.APPROVED
    gig.insight = post_insight

    monkeypatch.setattr("takumi.models.gig.Gig.is_live", mock.PropertyMock(return_value=True))
    monkeypatch.setattr(
        "takumi.models.gig.Gig.is_passed_claimable_time", mock.PropertyMock(return_value=True)
    )

    assert gig.is_claimable is True


def test_is_claimable_is_true_without_insight_if_skip_insights(monkeypatch, campaign, gig):
    campaign.require_insights = True
    gig.skip_insights = True

    monkeypatch.setattr("takumi.models.gig.Gig.is_live", mock.PropertyMock(return_value=True))
    monkeypatch.setattr(
        "takumi.models.gig.Gig.is_passed_claimable_time", mock.PropertyMock(return_value=True)
    )

    assert gig.insight is None
    assert gig.is_claimable is True


def test_is_live_hybrid_property_returns_true_if_approved_and_has_instagram_post(
    gig, instagram_post_factory
):
    # Arrange
    gig.instagram_post = instagram_post_factory(gig=gig)
    gig.state = GIG_STATES.APPROVED
    gig.is_verified = True

    # Act & Assert
    assert gig.is_live is True


def test_is_live_hybrid_property_returns_false_if_approved_and_not_posted(gig):
    # Arrange
    gig.is_verified = False
    gig.state = GIG_STATES.APPROVED

    # Act & Assert
    assert gig.is_live is False


def test_is_live_hybrid_property_returns_false_if_not_approved_and_has_instagram_post(
    gig, instagram_post_factory
):
    # Arrange
    gig.instagram_post = instagram_post_factory(gig=gig)
    gig.state = GIG_STATES.SUBMITTED

    # Act & Assert
    assert gig.is_live is False


def test_is_live_hybrid_property_returns_false_if_not_approved_and_no_instagram_post(gig):
    gig.instagram_post = None
    gig.state = GIG_STATES.SUBMITTED

    # Act & Assert
    assert gig.is_live is False


def test_end_of_review_period_returns_created_if_instagram_content_missing(gig, campaign):
    campaign.started = NEW_EXTENDED_CLAIM_HOURS_DATE - dt.timedelta(hours=1)
    created = NEW_EXTENDED_CLAIM_HOURS_DATE + dt.timedelta(hours=2)

    gig.instagram_post = None
    gig.instagram_story = None
    gig.is_verified = True
    gig.created = created

    assert gig.end_of_review_period == created


def test_gig_can_post_to_instagram_is_false_before_post_is_open(gig, post):
    gig.state = GIG_STATES.APPROVED

    with mock.patch("takumi.models.post.Post.is_open", mock.PropertyMock(return_value=False)):
        assert gig.can_post_to_instagram is False

    with mock.patch("takumi.models.post.Post.is_open", mock.PropertyMock(return_value=True)):
        assert gig.can_post_to_instagram is True


def test_gig_can_post_to_instagram_is_true_in_event_campaign_after_submitting(gig, post):
    post.requires_review_before_posting = False

    assert gig.can_post_to_instagram is True

    post.requires_review_before_posting = True

    assert gig.can_post_to_instagram is False


def test_gig_can_post_to_instagram_is_true_in_brand_safety_after_approving(gig, post):
    post.campaign.brand_safety = True
    gig.state = GIG_STATES.REVIEWED

    assert gig.can_post_to_instagram is False

    gig.state = GIG_STATES.APPROVED

    assert gig.can_post_to_instagram is True


def test_gig_can_post_to_instagram_is_true_after_submitting_in_non_brand_safety(gig, post):
    post.campaign.brand_safety = False
    gig.state = GIG_STATES.SUBMITTED

    assert gig.can_post_to_instagram is False

    gig.state = GIG_STATES.REVIEWED

    assert gig.can_post_to_instagram is True


def test_gig_can_post_to_instagram_is_false_if_campaign_is_reported(gig, post):
    gig.state = GIG_STATES.REPORTED
    post.campaign.brand_safety = True
    post.requires_review_before_posting = True

    assert gig.can_post_to_instagram is False

    post.campaign.brand_safety = False

    assert gig.can_post_to_instagram is False

    post.requires_review_before_posting = False

    assert gig.can_post_to_instagram is False

    gig.state = GIG_STATES.SUBMITTED

    assert gig.can_post_to_instagram is True
