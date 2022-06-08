import mock
import pytest
from mock import call

from takumi.gql.exceptions import PreconditionFailedException
from takumi.gql.mutation.influencer import (
    CancelInfluencerCooldown,
    CommentOnInfluencer,
    CooldownInfluencer,
    CreatePrewarmedInfluencer,
    DisableInfluencer,
    DismissInfluencerFollowerAnomalies,
    EnableInfluencer,
    MessageInfluencer,
    ReviewInfluencer,
    UnverifyInfluencer,
    UpdateInfluencer,
    VerifyInfluencer,
)
from takumi.models.offer import STATES as OFFER_STATES
from takumi.services import InstagramAccountService
from takumi.utils import uuid4_str


def test_cancel_influencer_cooldown_success(monkeypatch, influencer):
    # Arrange
    _stub_get_influencer(monkeypatch, influencer)

    # Act
    with mock.patch("takumi.gql.mutation.influencer.InfluencerService") as mock_influencer_service:
        CancelInfluencerCooldown().mutate("info", "id")

    # Assert
    service_calls = mock_influencer_service.return_value.__enter__.return_value
    assert service_calls.cancel_cooldown.called


def test_comment_on_influencer_success(monkeypatch, influencer):
    # Arrange
    _stub_get_influencer(monkeypatch, influencer)

    # Act
    with mock.patch("takumi.gql.mutation.influencer.InfluencerService") as mock_influencer_service:
        CommentOnInfluencer().mutate("info", "id", "comment")

    # Assert
    service_calls = mock_influencer_service.return_value.__enter__.return_value
    assert service_calls.comment_on.called
    assert service_calls.comment_on.call_args[0][0] == "comment"


def test_cooldown_influencer_success(monkeypatch, influencer):
    # Arrange
    _stub_get_influencer(monkeypatch, influencer)

    # Act
    with mock.patch("takumi.gql.mutation.influencer.InfluencerService") as mock_influencer_service:
        CooldownInfluencer().mutate("info", "id", "days")

    # Assert
    service_calls = mock_influencer_service.return_value.__enter__.return_value
    assert service_calls.cooldown.called
    assert service_calls.cooldown.call_args[0][0] == "days"


def test_disable_influencer_success(monkeypatch, influencer):
    # Arrange
    _stub_get_influencer(monkeypatch, influencer)

    # Act
    with mock.patch("takumi.gql.mutation.influencer.InfluencerService") as mock_influencer_service:
        DisableInfluencer().mutate("info", "id", "reason")

    # Assert
    service_calls = mock_influencer_service.return_value.__enter__.return_value
    assert service_calls.disable.called
    assert service_calls.disable.call_args[0][0] == "reason"


def test_disable_influencer_revokes_new_offers(monkeypatch, influencer, offer_factory):
    # Arrange
    _stub_get_influencer(monkeypatch, influencer)

    o1 = offer_factory(state=OFFER_STATES.INVITED, influencer=influencer)
    o2 = offer_factory(state=OFFER_STATES.ACCEPTED, influencer=influencer)

    # Act
    with mock.patch("takumi.gql.mutation.influencer.OfferService") as mock_offer_service:
        with mock.patch(
            "takumi.gql.mutation.influencer.InfluencerService"
        ) as mock_influencer_service:
            DisableInfluencer().mutate("info", "id", "reason")

    # Assert
    influencer_service_calls = mock_influencer_service.return_value.__enter__.return_value
    assert influencer_service_calls.disable.called
    assert influencer_service_calls.disable.call_args[0][0] == "reason"

    offer_service_calls = mock_offer_service.return_value.__enter__.return_value
    assert mock_offer_service.call_args[0][0] == o1
    assert mock_offer_service.call_args[0][0] != o2
    assert offer_service_calls.revoke.called


def test_enable_influencer_success(monkeypatch, influencer):
    # Arrange
    _stub_get_influencer(monkeypatch, influencer)

    # Act
    with mock.patch("takumi.gql.mutation.influencer.InfluencerService") as mock_influencer_service:
        EnableInfluencer().mutate("info", "id")

    # Assert
    service_calls = mock_influencer_service.return_value.__enter__.return_value
    assert service_calls.enable.called


def test_message_influencer_success(monkeypatch, influencer, developer_user):
    # Arrange
    _stub_get_influencer(monkeypatch, influencer)
    _stub_current_user(monkeypatch, developer_user)

    # Act
    with mock.patch("takumi.gql.mutation.influencer.InfluencerService") as mock_influencer_service:
        MessageInfluencer().mutate("info", "id", "text", "dm")

    # Assert
    service_calls = mock_influencer_service.return_value.__enter__.return_value
    assert service_calls.message.called
    assert service_calls.message.call_args == call(developer_user.ig_username, "text", "dm")


def test_review_influencer_success(monkeypatch, influencer, email_login):
    # Arrange
    _stub_get_influencer(monkeypatch, influencer)

    # Act
    with mock.patch("takumi.gql.mutation.influencer.InfluencerService") as mock_influencer_service:
        with mock.patch("takumi.gql.mutation.influencer.WelcomeEmail.send") as mock_welcome_email:
            ReviewInfluencer().mutate("info", "id")

    # Assert
    service_calls = mock_influencer_service.return_value.__enter__.return_value
    assert service_calls.review.called
    assert mock_welcome_email.called
    assert mock_welcome_email.call_args[0][0] == influencer.email


def test_unverify_influencer_success(monkeypatch, influencer):
    # Arrange
    _stub_get_influencer(monkeypatch, influencer)

    # Act
    with mock.patch("takumi.gql.mutation.influencer.InfluencerService") as mock_influencer_service:
        UnverifyInfluencer().mutate("info", "id")

    # Assert
    service_calls = mock_influencer_service.return_value.__enter__.return_value
    assert service_calls.unverify.called


def test_update_influencer_fails_if_gender_invalid(monkeypatch):
    # Arrange
    update_influencer = _get_update_influencer_skeleton()
    update_influencer["gender"] = "invalid gender"

    # Act
    with pytest.raises(PreconditionFailedException) as exc:
        UpdateInfluencer().mutate(**update_influencer)

    # Assert
    assert (
        '`Gender` must be either "female" or "male". Received "{}"'.format("invalid gender")
        in exc.exconly()
    )


def test_update_influencer_success(monkeypatch, influencer):
    # Arrange
    _stub_get_influencer(monkeypatch, influencer)

    update_influencer = _get_update_influencer_skeleton()
    update_influencer["interest_ids"] = ["id1", "id2"]
    update_influencer["gender"] = "male"
    update_influencer["birthday"] = "someday"
    update_influencer["target_region_id"] = "target_region_id"

    # Act
    with mock.patch("takumi.gql.mutation.influencer.InfluencerService") as mock_influencer_service:
        UpdateInfluencer().mutate(**update_influencer)

    # Assert
    service_calls = mock_influencer_service.return_value.__enter__.return_value
    assert call(update_influencer["interest_ids"]) in service_calls.update_interests.mock_calls
    assert call(update_influencer["gender"]) in service_calls.update_gender.mock_calls
    assert call(update_influencer["birthday"]) in service_calls.update_birthday.mock_calls
    assert (
        call(update_influencer["target_region_id"]) in service_calls.update_target_region.mock_calls
    )


def test_verify_influencer_success(monkeypatch, influencer):
    # Arrange
    _stub_get_influencer(monkeypatch, influencer)

    # Act
    with mock.patch("takumi.gql.mutation.influencer.InfluencerService") as mock_influencer_service:
        VerifyInfluencer().mutate("info", "id")

    # Assert
    service_calls = mock_influencer_service.return_value.__enter__.return_value
    assert service_calls.verify.called


def test_create_prewarmed_influencer(monkeypatch):
    # Act
    with mock.patch("takumi.gql.mutation.influencer.InfluencerService") as mock_influencer_service:
        CreatePrewarmedInfluencer().mutate("info", "username")

    # Assert
    assert mock_influencer_service.create_prewarmed_influencer.called


def test_dismiss_followers_anomalies_mutation_calls_instagram_account_service(
    influencer, monkeypatch
):
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)
    monkeypatch.setattr(
        "takumi.gql.mutation.influencer.get_influencer_or_404", lambda _: influencer
    )
    with mock.patch.object(
        InstagramAccountService, "dismiss_followers_anomalies"
    ) as mark_dismiss_mock:
        DismissInfluencerFollowerAnomalies().mutate("info", influencer.id)
    assert mark_dismiss_mock.called


#############################################
# Utility functions for tests defined below #
#############################################
@pytest.fixture(autouse=True, scope="module")
def _auto_stub_permission_decorator_required_for_mutations():
    with mock.patch("flask_principal.IdentityContext.can", return_value=True):
        yield


def _stub_get_influencer(monkeypatch, value):
    monkeypatch.setattr("takumi.gql.mutation.influencer.get_influencer_or_404", lambda x: value)


def _stub_current_user(monkeypatch, value):
    monkeypatch.setattr("takumi.gql.mutation.influencer.current_user", value)


def _get_update_influencer_skeleton():
    return {
        "info": "info",
        "id": uuid4_str(),
        "interest_ids": None,
        "gender": None,
        "birthday": None,
        "target_region_id": None,
    }
