import datetime as dt

import mock
from freezegun import freeze_time

from takumi.constants import WAIT_BEFORE_CLAIM_HOURS
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.user import EMAIL_NOTIFICATION_PREFERENCES
from takumi.tasks.scheduled.reapers import (
    client_notifications_daily_reaper,
    client_notifications_hourly_reaper,
)


@freeze_time("2017-01-01")
def test_offer_claimability_reaper(
    campaign, offer, post, gig_factory, instagram_post_factory, monkeypatch
):
    # Arrange
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr("takumi.tasks.scheduled.reapers._story_campaigns_quickfix", lambda: None)
    monkeypatch.setattr("takumi.tasks.scheduled.reapers._set_payable_date_if_missing", lambda: None)
    campaign.pre_approval = True

    first_gig = gig_factory(
        offer=offer,
        post=post,
        state=GIG_STATES.REQUIRES_RESUBMIT,
        instagram_post=instagram_post_factory(
            posted=dt.datetime.now(dt.timezone.utc)
            - dt.timedelta(hours=WAIT_BEFORE_CLAIM_HOURS + 48)
        ),
    )
    second_gig = gig_factory(
        offer=offer,
        post=post,
        state=GIG_STATES.APPROVED,
        instagram_post=instagram_post_factory(
            posted=dt.datetime.now(dt.timezone.utc)
            - dt.timedelta(days=WAIT_BEFORE_CLAIM_HOURS + 24)
        ),
        is_verified=True,
    )
    offer.gigs = [first_gig, second_gig]

    offer.payable = first_gig.end_of_review_period

    assert offer.payable.isoformat() != second_gig.end_of_review_period.isoformat()
    assert offer.has_all_gigs() is True
    assert offer.is_claimable is False


def test_client_notifications_reaper_sends_email_to_all_non_takumi_addresses(campaign, monkeypatch):
    # Arrange
    email_1 = "test1@example.com"
    email_2 = "test2@takumi.com"
    email_3 = "test3@example.com"
    campaign.advertiser = mock.MagicMock(
        users=[
            mock.Mock(
                email=email_1, email_notification_preference=EMAIL_NOTIFICATION_PREFERENCES.HOURLY
            ),
            mock.Mock(
                email=email_2, email_notification_preference=EMAIL_NOTIFICATION_PREFERENCES.HOURLY
            ),
            mock.Mock(
                email=email_3, email_notification_preference=EMAIL_NOTIFICATION_PREFERENCES.HOURLY
            ),
        ]
    )
    monkeypatch.setattr(
        "takumi.tasks.scheduled.reapers.CampaignService.get_campaigns_with_gigs_ready_for_approval",
        mock.Mock(return_value=[campaign]),
    )
    monkeypatch.setattr(
        "takumi.tasks.scheduled.reapers.CampaignService.get_campaigns_with_candidates_ready_for_review",
        mock.Mock(return_value=[campaign]),
    )

    # Act
    with mock.patch(
        "takumi.tasks.scheduled.reapers.GigReadyForApprovalEmail"
    ) as mock_gig_approval_email:
        with mock.patch(
            "takumi.tasks.scheduled.reapers.CandidatesReadyForReviewEmail"
        ) as mock_candidate_review_email:
            with mock.patch(
                "takumi.tasks.scheduled.reapers._notify_clients_that_have_unseen_comments"
            ):
                client_notifications_hourly_reaper()

    # Assert
    mock_gig_approval_email.return_value.send_many.assert_called_with([email_1, email_3])
    mock_candidate_review_email.return_value.send_many.assert_called_with([email_1, email_3])


def test_client_notifications_reaper_does_not_send_any_emails(campaign, monkeypatch):
    # Arrange
    monkeypatch.setattr(
        "takumi.tasks.scheduled.reapers.CampaignService.get_campaigns_with_gigs_ready_for_approval",
        mock.Mock(return_value=[]),
    )
    monkeypatch.setattr(
        "takumi.tasks.scheduled.reapers.CampaignService.get_campaigns_with_candidates_ready_for_review",
        mock.Mock(return_value=[]),
    )

    # Act
    with mock.patch(
        "takumi.tasks.scheduled.reapers.GigReadyForApprovalEmail"
    ) as mock_gig_approval_email:
        with mock.patch(
            "takumi.tasks.scheduled.reapers.GigReadyForApprovalEmail"
        ) as mock_candidate_review_email:
            with mock.patch(
                "takumi.tasks.scheduled.reapers._notify_clients_that_have_unseen_comments"
            ):
                client_notifications_hourly_reaper()

    # Assert
    assert not mock_gig_approval_email.return_value.send_many.called
    assert not mock_candidate_review_email.return_value.send_many.called


def test_client_notifications_reaper_doesnt_send_email_due_to_email_preferences(
    campaign, monkeypatch
):
    # Arrange
    email_1 = "test1@example.com"
    email_2 = "test2@takumi.com"
    email_3 = "test3@example.com"
    campaign.advertiser = mock.MagicMock(
        users=[
            mock.Mock(
                email=email_1, email_notification_preference=EMAIL_NOTIFICATION_PREFERENCES.HOURLY
            ),
            mock.Mock(
                email=email_2, email_notification_preference=EMAIL_NOTIFICATION_PREFERENCES.HOURLY
            ),
            mock.Mock(
                email=email_3, email_notification_preference=EMAIL_NOTIFICATION_PREFERENCES.HOURLY
            ),
        ]
    )
    monkeypatch.setattr(
        "takumi.tasks.scheduled.reapers.CampaignService.get_campaigns_with_gigs_ready_for_approval",
        mock.Mock(return_value=[campaign]),
    )
    monkeypatch.setattr(
        "takumi.tasks.scheduled.reapers.CampaignService.get_campaigns_with_candidates_ready_for_review",
        mock.Mock(return_value=[campaign]),
    )

    # Act
    with mock.patch(
        "takumi.tasks.scheduled.reapers.GigReadyForApprovalEmail"
    ) as mock_gig_approval_email:
        with mock.patch(
            "takumi.tasks.scheduled.reapers.CandidatesReadyForReviewEmail"
        ) as mock_candidate_review_email:
            with mock.patch(
                "takumi.tasks.scheduled.reapers._notify_clients_that_have_unseen_comments"
            ):
                client_notifications_daily_reaper()

    # Assert
    mock_gig_approval_email.return_value.send_many.assert_called_once_with([])
    mock_candidate_review_email.return_value.send_many.assert_called_once_with([])
