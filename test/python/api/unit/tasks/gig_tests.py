# encoding=utf-8

import mock

from takumi.events.gig import GigLog
from takumi.models.gig import STATES as GIG_STATES
from takumi.services.exceptions import CreateInstagramPostException, ServiceException
from takumi.tasks.gig import gig_check_submitted
from takumi.tasks.gig.link import link_gig
from takumi.tasks.gig.utils import report_gig
from takumi.validation.errors import ValidationError


def test_gig_check_posted_gig_does_not_report_a_payable_offer(posted_gig, monkeypatch):
    # Arrange
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: posted_gig)

    # Act
    posted_gig.offer.is_claimable = True
    with mock.patch(
        "takumi.tasks.gig.submitted.InstagramMediaValidator.from_gig"
    ) as mock_validator:
        gig_check_submitted(posted_gig.id)

    # Assert
    assert not mock_validator.called


def test_gig_check_submitted_tries_to_validate_a_non_payable_offer(posted_gig, monkeypatch):
    # Arrange
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: posted_gig)

    with mock.patch("takumi.models.Offer.is_claimable", False):
        with mock.patch(
            "takumi.tasks.gig.submitted.InstagramMediaValidator.from_gig"
        ) as mock_validator:
            gig_check_submitted(posted_gig.id)

    assert mock_validator.called


def test_gig_check_submitted_reports_gig_if_profile_validation_of_gig_failed(
    posted_gig, offer, monkeypatch
):
    # Arrange
    offer.is_claimable = False

    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: posted_gig)

    # Act
    with mock.patch("takumi.tasks.gig.submitted.report_gig") as mock_report_gig:
        with mock.patch(
            "takumi.tasks.gig.submitted.InstagramMediaValidator.from_gig"
        ) as mock_validator:
            mock_validator.return_value.validate.side_effect = [ValidationError("error")]
            gig_check_submitted(posted_gig.id)

    # Assert
    assert mock_report_gig.called


def test_report_gig_does_not_rereport_gig_already_reported(gig, monkeypatch):
    # Arrange
    gig.state = GIG_STATES.REPORTED

    mock_service = mock.MagicMock()
    monkeypatch.setattr("takumi.services.GigService", mock_service)

    # Act
    report_gig(gig, "reason")

    # Assert
    assert not mock_service.called


def test_report_gig_does_not_rereport_gig_for_same_reason(gig):
    gig.state = GIG_STATES.APPROVED

    with mock.patch("takumi.services.GigService") as mock_service_1:
        report_gig(gig, "a reason")

    assert mock_service_1.called

    log = GigLog(gig)
    log.add_event("report", {"reason": "different reason"})
    log.add_event("dismiss_report")

    with mock.patch("takumi.services.GigService") as mock_service_2:
        report_gig(gig, "a reason")

    assert mock_service_2.called

    log.add_event("report", {"reason": "a reason"})
    log.add_event("dismiss_report")

    with mock.patch("takumi.services.GigService") as mock_service_3:
        report_gig(gig, "a reason")

    assert not mock_service_3.called


def test_report_gig_reports_a_gig(gig, monkeypatch):
    # Arrange
    gig.state = GIG_STATES.SUBMITTED

    mock_service = mock.MagicMock()
    monkeypatch.setattr("takumi.services.GigService", mock_service)

    # Act
    report_gig(gig, "reason")

    # Assert
    assert mock_service.called


def test_report_gig_reports_log_exception_when_logging_fails(gig, monkeypatch):
    # Arrange
    gig.state = GIG_STATES.SUBMITTED

    monkeypatch.setattr(
        "takumi.services.GigService", mock.Mock(side_effect=[ServiceException("exc")])
    )

    # Act
    with mock.patch("takumi.tasks.gig.utils.slack.gig_log_exception") as mock_slack:
        report_gig(gig, "some reason")

    # Assert
    assert mock_slack.called


def test_link_gig_calls_create_instagram_post(gig, submission, monkeypatch):
    # Arrange
    media = {"id": "some_id"}
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: gig)
    monkeypatch.setattr(
        "takumi.tasks.gig.link.instascrape.get_post_by_caption", lambda *args, **kwargs: media
    )

    # Act
    with mock.patch("takumi.services.instagram_post.InstagramPostService.create") as mock_create:
        link_gig(gig.id)

    # Assert
    mock_create.assert_called_once_with(gig.id, media["id"])


def test_link_gig_raises_on_create_instagram_post(gig, submission, monkeypatch):
    # Arrange
    media = {"id": "some_id"}
    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: gig)
    monkeypatch.setattr(
        "takumi.tasks.gig.link.instascrape.get_post_by_caption", lambda *args, **kwargs: media
    )
    monkeypatch.setattr(
        "takumi.services.instagram_post.InstagramPostService.create",
        mock.Mock(side_effect=CreateInstagramPostException("message")),
    )

    # Act
    res = link_gig(gig.id)

    # Assert
    assert res == "Conditions not met: None"
