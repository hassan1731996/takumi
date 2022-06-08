import mock
import pytest

from takumi.gql.exceptions import GraphQLException
from takumi.gql.middlewares import DisableIntrospectionMiddleware


def test_disable_introspection_middleware_calls_next_when_not_introspection(app):
    mock_next = mock.Mock()
    mock_info = mock.Mock()
    mock_info.field_name = "currentUser"

    app.config["ALLOW_INTROSPECTION"] = False

    DisableIntrospectionMiddleware().resolve(mock_next, "root", mock_info)

    mock_next.assert_called_once_with("root", mock_info)


@pytest.mark.skip(
    reason="Need to figure out why g.identity is being populated for anonymous in test"
)
def test_disable_introspection_middleware_raises_if_introspection_and_anonymous(app):
    mock_next = mock.Mock()
    mock_info = mock.Mock()
    mock_info.field_name = "__introspection"

    app.config["ALLOW_INTROSPECTION"] = False

    with pytest.raises(GraphQLException, match="You need to be logged in"):
        DisableIntrospectionMiddleware().resolve(mock_next, "root", mock_info)

    assert not mock_next.called


def test_disable_introspection_middleware_allows_introspection_for_anonymous_if_config(app):
    mock_next = mock.Mock()
    mock_info = mock.Mock()
    mock_info.field_name = "__introspection"

    app.config["ALLOW_INTROSPECTION"] = True

    DisableIntrospectionMiddleware().resolve(mock_next, "root", mock_info)

    mock_next.assert_called_once_with("root", mock_info)


def test_disable_introspection_middleware_raises_if_introspection_and_influencer(
    app, client, influencer_user
):
    mock_next = mock.Mock()
    mock_info = mock.Mock()
    mock_info.field_name = "__introspection"

    app.config["ALLOW_INTROSPECTION"] = False
    influencer_user.email_login.email = "influencer@example.com"

    with client.user_request_context(influencer_user):
        with pytest.raises(GraphQLException, match="You need to be logged in"):
            DisableIntrospectionMiddleware().resolve(mock_next, "root", mock_info)

    assert not mock_next.called


def test_disable_introspection_middleware_calls_next_when_introspection_and_team_member(
    app, client, developer_user
):
    mock_next = mock.Mock()
    mock_info = mock.Mock()
    mock_info.field_name = "__introspection"

    app.config["ALLOW_INTROSPECTION"] = False

    with client.user_request_context(developer_user):
        DisableIntrospectionMiddleware().resolve(mock_next, "root", mock_info)

    mock_next.assert_called_once_with("root", mock_info)


def test_disable_introspection_middleware_calls_next_if_introspection_and_influencer_with_allowed_domain(
    app, client, influencer_user
):
    mock_next = mock.Mock()
    mock_info = mock.Mock()
    mock_info.field_name = "__introspection"

    app.config["ALLOW_INTROSPECTION"] = False
    influencer_user.email_login.email = "influencer@takumi.com"

    with client.user_request_context(influencer_user):
        DisableIntrospectionMiddleware().resolve(mock_next, "root", mock_info)

    mock_next.assert_called_once_with("root", mock_info)
