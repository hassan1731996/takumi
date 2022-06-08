# encoding=utf-8

import mock
import pytest

from core.common.exceptions import APIError

from takumi.auth import influencer_required
from takumi.constants import MINIMUM_CLIENT_VERSION


def get_mock_view():
    view = mock.Mock()
    view.__name__ = "view"
    return view


def test_influencer_required_api_error_with_401_if_user_is_not_influencer(
    client, advertiser_user, monkeypatch
):
    view = get_mock_view()

    with pytest.raises(APIError) as exc:
        with client.use(advertiser_user):
            influencer_required(view)()

    assert not view.called
    assert exc.value.status_code == 401


def test_influencer_required_throws_401_if_user_doesnt_have_instagram_account_on_min_version(
    influencer, influencer_user, client, monkeypatch
):

    monkeypatch.setattr(
        "takumi.exceptions.get_request_version", lambda *args: MINIMUM_CLIENT_VERSION
    )
    influencer.instagram_account = None

    view = get_mock_view()

    with pytest.raises(APIError) as exc:
        with client.use(influencer_user):
            influencer_required(view)()

    assert not view.called
    assert exc.value.status_code == 401


def test_influencer_required_allows_influencers_with_instagram_account_on_min_version(
    influencer, instagram_account, influencer_user, client, monkeypatch
):

    influencer.instagram_account = instagram_account

    monkeypatch.setattr("takumi.auth.current_user", influencer.user)
    monkeypatch.setattr(
        "takumi.exceptions.get_request_version", lambda *args: MINIMUM_CLIENT_VERSION
    )

    view = get_mock_view()
    with client.user_request_context(influencer_user):
        influencer_required(view)()

    assert view.called


def test_influencer_required_raises_401_if_influncer_is_forced_to_log_out(
    influencer, instagram_account, influencer_user, client, monkeypatch
):

    influencer.instagram_account = instagram_account

    monkeypatch.setattr("takumi.auth.current_user", influencer.user)
    monkeypatch.setattr(
        "takumi.exceptions.get_request_version", lambda *args: MINIMUM_CLIENT_VERSION
    )

    influencer.force_logout(True)

    view = get_mock_view()
    with pytest.raises(APIError) as exc:
        with client.use(influencer_user):
            influencer_required(view)()

    assert not view.called
    assert exc.value.status_code == 401
