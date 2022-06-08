import mock
import pytest
from flask_login import current_user

from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.gig import (
    DismissGigReport,
    LinkGig,
    MarkAsPosted,
    RequestGigResubmission,
    RevertGigReport,
    ReviewGig,
)
from takumi.models.gig import STATES
from takumi.services import GigService, InstagramPostService


def test_review_gig_mutation_calls_gig_service(gig, monkeypatch):
    gig.state = STATES.SUBMITTED
    current_user.id = "very_valid_test_uuid"

    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("flask_principal.IdentityContext.can", lambda _: True)
    monkeypatch.setattr("takumi.gql.mutation.gig.get_gig_or_404", lambda _: gig)

    with mock.patch.object(GigService, "review_gig") as review_gig_mock:
        ReviewGig().mutate("info", gig.id)

    review_gig_mock.assert_called_once_with(current_user.id)


# Missing test for report gig


def test_dismiss_report_mutation_calls_gig_service(gig, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("flask_principal.IdentityContext.can", lambda _: True)
    monkeypatch.setattr("takumi.gql.mutation.gig.get_gig_or_404", lambda _: gig)

    with mock.patch.object(GigService, "dismiss_report") as dismiss_report_mock:
        DismissGigReport().mutate("info", gig.id)
        dismiss_report_mock.assert_called_once_with()


def test_revert_report_mutation_calls_gig_service(gig, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("flask_principal.IdentityContext.can", lambda _: True)
    monkeypatch.setattr("takumi.gql.mutation.gig.get_gig_or_404", lambda _: gig)

    with mock.patch.object(GigService, "revert_report") as dismiss_report_mock:
        RevertGigReport().mutate("info", gig.id)
        dismiss_report_mock.assert_called_once_with()


def test_request_resubmission_mutation_calls_gig_service(gig, monkeypatch):
    # Arrange
    reason = "reason"
    explanation = "explanation"

    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("flask_principal.IdentityContext.can", lambda _: True)
    monkeypatch.setattr("takumi.gql.mutation.gig.get_gig_or_404", lambda _: gig)

    # Act
    with mock.patch.object(GigService, "request_resubmission") as request_resubmission_mock:
        with mock.patch("takumi.gql.mutation.gig.ResubmitGigEmail") as resubmit_email_mock:
            RequestGigResubmission().mutate(
                "info", gig.id, send_email=True, reason=reason, explanation=explanation
            )

    # Assert
    request_resubmission_mock.assert_called_once_with(reason=reason, explanation=explanation)
    assert resubmit_email_mock.called


def test_link_gig_calls_create_class_method_from_instagram_post_service(gig, monkeypatch):
    # Arrange
    shortcode = "shortcode"

    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("takumi.gql.mutation.gig.permissions.link_gig.can", lambda *args: True)
    monkeypatch.setattr("takumi.gql.mutation.gig.get_gig_or_404", lambda _: gig)

    # Act
    with mock.patch.object(InstagramPostService, "create") as mock_create_instagram_post:
        LinkGig().mutate("info", gig.id, shortcode=shortcode)

    # Assert
    mock_create_instagram_post.assert_called_once_with(gig.id, shortcode)


def test_link_gig_raises_if_instagram_post_exists_and_doesnt_have_permission(
    posted_gig, monkeypatch
):
    # Arrange
    shortcode = "shortcode"

    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("takumi.gql.mutation.gig.permissions.link_gig.can", lambda *args: False)
    monkeypatch.setattr("takumi.gql.mutation.gig.get_gig_or_404", lambda _: posted_gig)

    # Act
    with pytest.raises(MutationException) as exc:
        LinkGig().mutate("info", posted_gig.id, shortcode=shortcode)

    # Assert
    assert "You don't have a permission to link <Gig: {}>".format(posted_gig.id) in exc.exconly()


def test_link_gig_calls_create_class_method_from_instagram_post_service_after_unlinking(
    posted_gig, monkeypatch
):
    # Arrange
    shortcode = "shortcode"

    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("takumi.gql.mutation.gig.permissions.link_gig.can", lambda *args: True)
    monkeypatch.setattr("takumi.gql.mutation.gig.get_gig_or_404", lambda _: posted_gig)

    # Act
    with mock.patch.object(InstagramPostService, "unlink_gig") as mock_unlink_gig:
        with mock.patch.object(InstagramPostService, "create") as mock_create_gig:
            LinkGig().mutate("info", posted_gig.id, shortcode=shortcode)

    # Assert
    mock_unlink_gig.assert_called_once()
    mock_create_gig.assert_called_once_with(posted_gig.id, shortcode)


def test_mark_as_posted_mutation_calls_gig_service(gig, monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr("flask_principal.IdentityContext.can", lambda _: True)
    monkeypatch.setattr("takumi.gql.mutation.gig.get_gig_or_404", lambda _: gig)

    with mock.patch.object(GigService, "mark_as_posted") as mark_as_posted_mock:
        MarkAsPosted().mutate("info", gig.id, True)

    mark_as_posted_mock.assert_called_once_with(True)
