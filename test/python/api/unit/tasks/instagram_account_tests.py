import mock

from takumi.models import InstagramAccount
from takumi.tasks.instagram_account import set_instagram_account_username


def test_update_instagram_account_username_frees_up_used_username(
    client, instagram_account, monkeypatch
):
    in_use_username = "in_use"
    old_user = InstagramAccount(ig_username=in_use_username, id="old_id")

    mock_instagram_account = mock.Mock()
    mock_instagram_account.by_username.return_value = old_user

    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr("takumi.tasks.instagram_account.InstagramAccount", mock_instagram_account)

    assert instagram_account.ig_username != in_use_username

    with mock.patch("takumi.tasks.instagram_account.instagram_account_new_username") as mock_task:
        set_instagram_account_username(instagram_account, in_use_username)

    assert instagram_account.ig_username == in_use_username
    mock_task.delay.assert_called_with("old_id")


def test_update_instagram_account_username_updates_influencer_username(
    client, instagram_account, monkeypatch
):
    assert instagram_account.ig_username != "new_username"

    mock_instagram_account = mock.Mock()
    mock_instagram_account.by_username.return_value = None

    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr("takumi.tasks.instagram_account.InstagramAccount", mock_instagram_account)

    set_instagram_account_username(instagram_account, "new_username")

    assert instagram_account.ig_username == "new_username"
