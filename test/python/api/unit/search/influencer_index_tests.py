import mock
import pytest

from takumi.models import Audit, Influencer, InstagramAccount, Offer, User
from takumi.search.influencer import (
    trigger_influencer_info_update,
    trigger_influencer_info_update_for_audit,
    trigger_influencer_info_update_for_instagram_account,
    trigger_influencer_info_update_for_offer,
    trigger_influencer_info_update_for_user,
)
from takumi.search.influencer import update_influencer_info as real_update_influencer_info


@pytest.fixture(autouse=True, scope="module")
def load_app(app):
    yield


@pytest.fixture(autouse=True, scope="function")
def update_influencer_info():
    with mock.patch("takumi.search.influencer.update_influencer_info") as m:
        yield m


def test_trigger_influencer_info_update_from_audit(update_influencer_info):
    ig_acc = InstagramAccount()
    influencer = Influencer(id="test-456", instagram_account=ig_acc)
    audit = Audit(influencer=influencer)

    ig_acc.influencer = influencer
    trigger_influencer_info_update_for_audit(None, None, audit)
    assert update_influencer_info.delay.called_with(influencer.id, "audit")


def test_trigger_influencer_info_update_from_user(monkeypatch, update_influencer_info):
    ig_acc = InstagramAccount()
    user = User(id="test-123")
    influencer = Influencer(id="test-456", user=user, instagram_account=ig_acc)

    user.influencer = influencer
    ig_acc.influencer = influencer
    trigger_influencer_info_update_for_user(None, None, user)
    assert update_influencer_info.delay.called_with(influencer.id, "device")


def test_trigger_influencer_info_update_from_instagram_account(update_influencer_info):
    ig_acc = InstagramAccount()
    influencer = Influencer(id="test-123", instagram_account=ig_acc)
    ig_acc.influencer = influencer
    trigger_influencer_info_update_for_instagram_account(None, None, ig_acc)
    assert update_influencer_info.delay.called_with(influencer.id, "instagram_account")


def test_trigger_influencer_info_update_from_instagram_account_without_influencer(
    update_influencer_info,
):
    ig_acc = InstagramAccount()
    with mock.patch(
        "takumi.search.influencer.indexing.capture_exception"
    ) as mock_capture_exception:
        trigger_influencer_info_update_for_instagram_account(None, None, ig_acc)
    assert not update_influencer_info.delay.called
    assert not mock_capture_exception.called


def test_trigger_influencer_info_update_from_influencer(update_influencer_info):
    ig_acc = InstagramAccount()
    influencer = Influencer(id="test-123", instagram_account=ig_acc)
    ig_acc.influencer = influencer
    trigger_influencer_info_update(None, None, influencer)
    assert update_influencer_info.delay.called_with(influencer.id, "influencer")


def test_trigger_influencer_info_update_from_influencer_without_instagram_account(
    update_influencer_info,
):
    influencer = Influencer(id="test-123")
    trigger_influencer_info_update(None, None, influencer)
    assert not update_influencer_info.delay.called


def test_trigger_influencer_info_update_from_offer(update_influencer_info):
    ig_acc = InstagramAccount()
    influencer = Influencer(id="test-123", instagram_account=ig_acc)
    ig_acc.influencer = influencer
    offer = Offer(influencer=influencer)
    trigger_influencer_info_update_for_offer(None, None, offer)
    assert update_influencer_info.delay.called_with(influencer.id, "offer")


def test_trigger_influencer_info_update_from_offer_without_influencer_instagram_account(
    update_influencer_info,
):
    influencer = Influencer(id="test-123")
    offer = Offer(influencer=influencer)
    trigger_influencer_info_update_for_offer(None, None, offer)
    assert not update_influencer_info.delay.called


def test_trigger_influencer_info_update_metric_emission(app):
    ig_acc = InstagramAccount()
    influencer = Influencer(id="test-123", instagram_account=ig_acc)
    ig_acc.influencer = influencer
    with mock.patch("takumi.search.influencer.indexing.InfluencerIndex.update_from_source"):
        real_update_influencer_info(influencer.id, source="testing")

    call = app.config["statsd"].timing.call_args_list[-2]
    assert call[0][0] == "takumi.search.influencer.update_influencer_info"
    assert call[1]["tags"][0] == "source:testing"
