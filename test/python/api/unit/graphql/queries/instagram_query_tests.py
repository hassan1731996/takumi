import mock

from takumi.gql.query.instagram import InstagramQuery


def test_resolve_instagram_user_empty_name():
    result = InstagramQuery().resolve_instagram_user(info="info")
    assert result is None


def test_resolve_instagram_user_returns_name():
    with mock.patch(
        "takumi.gql.query.instagram.instascrape.get_user", return_value="insta_name"
    ) as mock_get:
        result = InstagramQuery().resolve_instagram_user(info="info", username="name")
    mock_get.assert_called_once_with("name")
    assert result == "insta_name"


def test_resolve_instagram_user_raise_error():
    with mock.patch("takumi.gql.query.instagram.instascrape.get_user") as mock_get:
        mock_get.side_effect = Exception("some error")
        result = InstagramQuery().resolve_instagram_user(info="info", username="name")
    mock_get.assert_called_once_with("name")
    assert result is None
