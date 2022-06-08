# encoding=utf-8
import mock
import pytest

from takumi.models.gig import STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.services.gig import (
    GigAlreadySubmittedException,
    GigInvalidCaptionException,
    GigInvalidStateException,
    GigReportException,
    GigResubmissionException,
    GigService,
    OfferNotAcceptedException,
    OfferNotFoundException,
)
from takumi.utils import uuid4_str


def test_gig_service_get_by_id(db_gig):
    gig = GigService.get_by_id(db_gig.id)
    assert gig == db_gig


def test_gig_service_review_gig_fails_if_gig_is_reported(db_session, db_gig, db_developer_user):
    # Arrange
    db_gig.state = STATES.REPORTED
    db_gig.offer.campaign.pre_approval = True
    db_session.commit()  # Make sure that we don't start GigService with a dirty gig

    # Act
    with pytest.raises(GigInvalidStateException) as exc:
        GigService(db_gig).review_gig(db_developer_user.id)

    # Assert
    assert "Only gigs submitted for review can be reviewed" in exc.exconly()


def test_gig_service_review_success(db_session, db_gig, db_developer_user):
    # Arrange
    assert db_gig.reviewer_id is None
    db_gig.state = STATES.SUBMITTED
    db_session.commit()

    # Act
    with GigService(db_gig) as service:
        service.review_gig(db_developer_user.id)

    # Assert
    assert db_gig.reviewer_id == db_developer_user.id


def test_gig_service_review_reviews_and_approves(db_session, db_gig, db_developer_user):
    # Arrange
    assert db_gig.reviewer_id is None
    db_gig.post.campaign.brand_safety = False
    db_gig.state = STATES.SUBMITTED
    db_session.commit()

    # Act
    with GigService(db_gig) as service:
        service.review_gig(db_developer_user.id)

    # Assert
    assert db_gig.reviewer_id == db_developer_user.id
    assert db_gig.state == STATES.APPROVED


def test_gig_service_reviews_and_schedules_approval_deadline(db_session, db_gig, db_developer_user):
    # Arrange
    assert db_gig.reviewer_id is None
    db_gig.post.campaign.brand_safety = True
    db_gig.state = STATES.SUBMITTED
    db_session.commit()

    # Act
    with GigService(db_gig) as service:
        service.review_gig(db_developer_user.id)

    # Assert
    assert db_gig.reviewer_id == db_developer_user.id
    assert db_gig.state == STATES.REVIEWED


def test_gig_service_approve_success(db_session, db_gig, db_developer_user):
    # Arrange
    assert db_gig.approver_id is None
    db_gig.state = STATES.REVIEWED
    db_session.commit()

    # Act
    with GigService(db_gig) as service:
        service.approve_gig(db_developer_user.id)

    # Assert
    assert db_gig.approver_id == db_developer_user.id


def test_gig_service_report_gig_fails_if_gig_not_in_submitted_state(
    db_session, db_gig, db_advertiser_user
):
    # Arrange
    db_gig.state = STATES.REQUIRES_RESUBMIT
    db_session.commit()  # Make sure that we don't start GigService with a dirty gig

    # Act
    with pytest.raises(GigReportException) as exc:
        GigService(db_gig).report_gig("reason", db_advertiser_user)

    # Assert
    assert "Can only report reviewed or approved gigs" in exc.exconly()


def test_gig_service_report_gig_success(db_session, db_gig, db_advertiser_user):
    # Arrange
    db_gig.state = STATES.APPROVED
    db_session.commit()  # Make sure that we don't start GigService with a dirty gig

    # Act
    with GigService(db_gig) as service:
        service.report_gig("reason", db_advertiser_user)

    # Assert
    assert db_gig.report_reason == "reason"
    assert db_gig.state == STATES.REPORTED


def test_gig_service_request_resubmission_fails_if_gig_not_in_valid_state(db_session, db_gig):
    # Arrange
    db_gig.state = STATES.APPROVED
    db_session.commit()  # Make sure that we don't start GigService with a dirty gig

    # Act
    with pytest.raises(GigResubmissionException) as exc:
        GigService(db_gig).request_resubmission("reason", "explanation")

    # Assert
    assert "Gig has to be submitted or reported to request resubmission" in exc.exconly()


def test_gig_service_request_resubmission_success(monkeypatch, db_session, db_gig):
    # Arrange
    monkeypatch.setattr("takumi.gql.mutation.gig.ResubmitGigEmail.send", lambda *args: None)
    db_gig.state = STATES.REPORTED
    db_session.commit()  # Make sure that we don't start GigService with a dirty gig

    # Act
    with GigService(db_gig) as service:
        service.request_resubmission("reason", "explanation")

    # Assert
    assert db_gig.state == STATES.REQUIRES_RESUBMIT


def test_gig_service_request_resubmission_unlinks_post(monkeypatch, db_session, db_instagram_post):
    # Arrange
    gig = db_instagram_post.gig
    monkeypatch.setattr("takumi.gql.mutation.gig.ResubmitGigEmail.send", lambda *args: None)
    gig.state = STATES.REPORTED
    db_session.commit()  # Make sure that we don't start GigService with a dirty gig

    # Act
    with GigService(gig) as service:
        service.request_resubmission("reason", "explanation")

    # Assert
    assert gig.state == STATES.REQUIRES_RESUBMIT

    assert gig.instagram_post is None


def test_gig_service_request_resubmission_unlinks_story(
    monkeypatch, db_session, db_instagram_story
):
    # Arrange
    gig = db_instagram_story.gig
    monkeypatch.setattr("takumi.gql.mutation.gig.ResubmitGigEmail.send", lambda *args: None)
    gig.state = STATES.REPORTED
    db_session.commit()  # Make sure that we don't start GigService with a dirty gig

    # Act
    with GigService(gig) as service:
        service.request_resubmission("reason", "explanation")

    # Assert
    assert gig.state == STATES.REQUIRES_RESUBMIT

    assert gig.instagram_story is None


def test_gig_service_create_succeeds_on_accepted_offer(db_offer, db_post):
    # Arrange
    db_offer.state = OFFER_STATES.ACCEPTED

    # Act
    gig = GigService.create(db_offer.id, db_post.id)
    with GigService(gig) as service:
        service.create_submission(media=[{"type": "image", "url": "http://"}], caption="Whoa there")

    # Assert
    assert gig.state == STATES.SUBMITTED
    assert gig.submission is not None
    assert gig.submission.caption == "Whoa there"
    assert len(gig.submission.media) == 1
    assert gig.submission.media[0].url == "http://"


def test_gig_service_create_fails_on_non_existing_offer(db_post):
    # Act
    with pytest.raises(OfferNotFoundException) as exc:
        GigService.create(uuid4_str(), db_post.id)

    # Assert
    assert "Could not find offer" in exc.exconly()


def test_gig_service_create_fails_on_non_accepted_offer(db_post, db_offer):
    # Arrange
    db_offer.state = OFFER_STATES.INVITED

    # Act
    with pytest.raises(OfferNotAcceptedException) as exc:
        GigService.create(db_offer.id, db_post.id)

    # Assert
    assert "Offer is not in accepted state" in exc.exconly()


def test_gig_service_create_fails_on_double_submission(db_offer, db_post):
    # Arrange
    db_offer.state = OFFER_STATES.ACCEPTED
    # Act
    gig = GigService.create(db_offer.id, db_post.id)
    with GigService(gig) as service:
        service.create_submission(
            media=[{"type": "image", "url": "http://image.jpg"}], caption="Whoa there"
        )

    with pytest.raises(
        GigAlreadySubmittedException, match="Can only create a submission when gig is new"
    ):
        with GigService(gig) as service:
            service.create_submission(
                media=[{"type": "image", "url": "http://image.jpg"}], caption="Whoa there"
            )


def test_gig_service_create_fails_on_invalid_caption(db_offer, db_post):
    # Arrange
    db_offer.state = OFFER_STATES.ACCEPTED
    db_post.conditions = [{"type": "hashtag", "value": "ad"}]

    # Act
    gig = GigService.create(db_offer.id, db_post.id)

    with pytest.raises(GigInvalidCaptionException, match="Missing hashtag: #ad"):
        with GigService(gig) as service:
            service.create_submission(
                media=[{"type": "image", "url": "http://image.jpg"}], caption="Invalid"
            )


def test_create_gig_creates_a_gig_with_gallery(db_offer, db_post):
    # Arrange
    db_offer.state = OFFER_STATES.ACCEPTED
    media = [
        {"type": "image", "url": "https://1"},
        {"type": "image", "url": "https://2"},
        {"type": "image", "url": "https://3"},
    ]
    db_post.gallery_photo_count = 2

    # Act
    gig = GigService.create(db_offer.id, db_post.id)
    with GigService(gig) as service:
        service.create_submission(media=media, caption="Caption without hashtag")

    # Assert
    assert gig.submission is not None

    media = gig.submission.media

    assert len(media) == 3

    assert ["https://1", "https://2", "https://3"] == sorted([m.url for m in media])


def test_reject_gig_rejects_the_gig(db_session, db_gig):
    # Arrange
    db_gig.state = STATES.REPORTED
    db_session.commit()  # Make sure that we don't start GigService with a dirty gig

    # Act
    with GigService(db_gig) as service:
        service.reject("reason")

    # Assert
    assert db_gig.reject_reason == "reason"
    assert db_gig.state == STATES.REJECTED


def test_reject_gig_sets_offer_to_claimable_if_all_gigs_are_claimable(db_session, db_gig):
    # Arrange
    db_gig.state = STATES.REPORTED
    db_session.commit()  # Make sure that we don't start GigService with a dirty gig

    assert db_gig.offer.has_all_gigs() is False
    assert db_gig.offer.has_all_gigs_claimable() is False
    assert db_gig.offer.is_claimable is False

    # Act
    with GigService(db_gig) as service:
        service.reject("reason")

    # Assert
    assert db_gig.offer.has_all_gigs() is True
    assert db_gig.offer.has_all_gigs_claimable() is True
    assert db_gig.offer.is_claimable is True


def test_reject_gig_schedules_is_claimable_check_if_offer_has_all_gigs(
    monkeypatch, db_campaign, db_offer, gig_factory, instagram_post_factory
):
    # Arrange
    from takumi.services import PostService

    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.post_count", mock.PropertyMock(return_value=2)
    )
    PostService.create_post(db_campaign.id)
    PostService.create_post(db_campaign.id)

    gig_factory(
        post=db_campaign.posts[0],
        offer=db_offer,
        state=STATES.APPROVED,
        instagram_post=instagram_post_factory(),
        is_verified=True,
    )
    gig_to_be_rejected = gig_factory(
        post=db_campaign.posts[1], offer=db_offer, state=STATES.REPORTED
    )

    assert db_offer.has_all_gigs() is False
    assert db_offer.has_all_gigs_claimable() is False
    assert db_offer.is_claimable is False
    assert db_offer.scheduled_jobs == {}

    # Act
    with GigService(gig_to_be_rejected) as service:
        service.reject("reason")

    # Assert
    assert db_offer.has_all_gigs() is True
    assert db_offer.has_all_gigs_claimable() is False
    assert db_offer.is_claimable is False
    assert db_offer.scheduled_jobs == {}


def test_get_latest_influencer_gig_of_a_post_returns_none(db_post, db_influencer):
    # Arrange
    db_post.gigs = []

    # Act
    result = GigService.get_latest_influencer_gig_of_a_post(db_influencer.id, db_post.id)

    # Assert
    assert result is None


def test_get_latest_influencer_require_resubmit_gig_of_a_post_returns_none(db_post, db_influencer):
    # Arrange
    db_post.gigs = []

    # Act
    result = GigService.get_latest_influencer_require_resubmit_gig_of_a_post(
        db_influencer.id, db_post.id
    )

    # Assert
    assert result is None


def test_create_submission_adds_a_submission_to_get_gig(db_gig, db_session):
    db_gig.state = STATES.SUBMITTED
    db_session.commit()

    with GigService(db_gig) as service:
        service.create_submission("the caption", [{"type": "image", "url": "http://image.jpg"}])

    assert db_gig.submission is not None
    assert db_gig.submission.caption == "the caption"
    assert db_gig.submission.media[0].url == "http://image.jpg"
    assert db_gig.submission.media[0].owner_type == "submission"
