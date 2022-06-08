import mock

from takumi.events.influencer import InfluencerLog
from takumi.influencers import register_hashed_bank_destination
from takumi.models import Gig, Influencer
from takumi.utils import uuid4_str


def _gig(reward, influencer, post, state="submitted"):
    return Gig(id=uuid4_str(), state=state, influencer=influencer, post=post, media=[], events=[])


def test_register_hashed_bank_destination(influencer):
    assert "hashed_iban" not in influencer.info
    with mock.patch("flask_sqlalchemy.BaseQuery.all") as mock_all:
        mock_all.return_value = []
        register_hashed_bank_destination(influencer, "foo")
    assert influencer.info["hashed_bank_destination"]


def test_register_hashed_bank_destination_notifies_support_on_slack_if_destination_in_use(
    influencer, influencer_user, client, slack_post
):
    with client.user_request_context(influencer_user):
        assert "hashed_iban" not in influencer.info
        other_influencer = Influencer(id=uuid4_str())
        with mock.patch("flask_sqlalchemy.BaseQuery.all") as mock_all:
            mock_all.return_value = [other_influencer]
            register_hashed_bank_destination(influencer, "foo")
        assert influencer.info["hashed_bank_destination"]
        assert slack_post.called


MOCK_RECENT_MEDIA = [
    {"likes": {"count": 100}, "comments": {"count": 10}},
    {"likes": {"count": 200}, "comments": {"count": 20}},
    {"likes": {"count": 300}, "comments": {"count": 30}},
    {"likes": {"count": 400}, "comments": {"count": 40}},
]


def test_influencer_force_logout_false_if_no_info(influencer):
    influencer.info = None
    assert influencer.force_logout() is False


def test_influencer_force_logout_false_if_no_force_logout_in_info(influencer):
    influencer.info = {}
    assert influencer.force_logout() is False


def test_influencer_force_logout_true_if_force_logout_true_in_info(influencer):
    influencer.info = {"force_logout": True}
    assert influencer.force_logout() is True

    influencer.info["force_logout"] = False
    assert influencer.force_logout() is False


def test_influencer_force_logout_false_if_force_logout_is_non_bool(influencer):
    influencer.info = {"force_logout": "homer simpson"}
    assert influencer.force_logout() is False


def test_influencer_force_logout_sets_and_returns(influencer):
    assert influencer.force_logout() is False

    influencer.force_logout(True)
    assert influencer.force_logout() is True
    assert influencer.info is not None


def test_influencer_log_set_target_region(influencer):
    log = InfluencerLog(influencer)
    log.add_event("set_target_region", {"region_id": "1234"})
    assert influencer.target_region_id == "1234"


def test_influencer_log_set_current_region(influencer):
    log = InfluencerLog(influencer)
    log.add_event("set_current_region", {"region_id": "1234"})
    assert influencer.current_region_id == "1234"
