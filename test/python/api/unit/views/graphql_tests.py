# encoding: utf-8
import graphene
import mock
import pytest
from flask import url_for

from core.common.exceptions import APIError

from takumi.gql import fields
from takumi.roles import permissions
from takumi.validation.errors import MissingHashtagError
from takumi.views.gql import GraphQLView


class PublicQuery:
    public_string = fields.String()
    guarded_string = fields.String()

    @permissions.public.require()
    def resolve_public_string(root, info):
        return "public string"

    @permissions.influencer.require()
    def resolve_guarded_string(root, info):
        return "guarded string"


class PrivateQuery:
    private_string = fields.String()

    @permissions.public.require()
    def resolve_private_string(root, info):
        return "private string"


@pytest.fixture(scope="function")
def public_schema():
    class Query(graphene.ObjectType, PublicQuery):
        pass

    yield graphene.Schema(query=Query)


@pytest.fixture(scope="function")
def private_schema():
    class Query(graphene.ObjectType, PublicQuery, PrivateQuery):
        pass

    yield graphene.Schema(query=Query)


def test_graphqlview_format_error_with_errors(monkeypatch, public_schema):
    with mock.patch.object(
        GraphQLView, "schema", new_callable=mock.PropertyMock, return_value=public_schema
    ):
        view = GraphQLView(schema=public_schema)

    exception = Exception()
    exception.original_error = Exception()
    exception.original_error.errors = [
        MissingHashtagError("foo"),
        MissingHashtagError("það"),
        MissingHashtagError("FürDieKostenübernahme"),
    ]

    formatted = view.format_error(exception)

    assert formatted["errors"] == [
        "Missing hashtag: #foo",
        "Missing hashtag: #það",
        "Missing hashtag: #FürDieKostenübernahme",
    ]


def test_graphqlview_format_error_with_permission_exceptions(client, public_schema, monkeypatch):
    monkeypatch.setattr("takumi.views.gql.schema", private_schema)
    monkeypatch.setattr("takumi.views.gql.public_schema", public_schema)

    query = "{guardedString}"

    result = client.query(url_for("api.graphql"), query)

    assert "errors" in result.json
    assert len(result.json["errors"]) == 1
    error = result.json["errors"][0]

    assert "You do not have permission to do that" in error["message"]
    assert error["type"] == "PermissionDenied"


def test_graphql_anonymous_user_sees_public_schema(
    private_schema, public_schema, client, monkeypatch
):
    monkeypatch.setattr("takumi.views.gql.schema", private_schema)
    monkeypatch.setattr("takumi.views.gql.public_schema", public_schema)

    query = "{publicString}"

    result = client.query(url_for("api.graphql"), query)

    assert result.json["data"]["publicString"] == "public string"


def test_graphql_anonymous_user_doesnt_see_private_schema(
    private_schema, public_schema, client, monkeypatch
):
    monkeypatch.setattr("takumi.views.gql.schema", private_schema)
    monkeypatch.setattr("takumi.views.gql.public_schema", public_schema)

    query = "{privateString}"

    result = client.query(url_for("api.graphql"), query)

    assert result.status_code == 401


def test_graphql_logged_in_user_sees_public_schema(
    private_schema, public_schema, client, advertiser_user, monkeypatch
):
    monkeypatch.setattr("takumi.views.gql.schema", private_schema)
    monkeypatch.setattr("takumi.views.gql.public_schema", public_schema)

    query = "{publicString}"

    with client.use(advertiser_user):
        result = client.query(url_for("api.graphql"), query)

    assert result.json["data"]["publicString"] == "public string"


def test_graphql_logged_in_user_sees_private_schema(
    private_schema, public_schema, client, advertiser_user, monkeypatch
):
    monkeypatch.setattr("takumi.views.gql.schema", private_schema)
    monkeypatch.setattr("takumi.views.gql.public_schema", public_schema)

    query = "{privateString}"

    with client.use(advertiser_user):
        result = client.query(url_for("api.graphql"), query)

    assert result.json["data"]["privateString"] == "private string"


def test_graphql_authentication_middleware_with_anonymous_user(client, monkeypatch):
    class Query(graphene.ObjectType):
        public_string = fields.String()
        masked_string = fields.AuthenticatedField(fields.String, needs=mock.Mock())

        @permissions.public.require()
        def resolve_public_string(root, info):
            return "public string"

        @permissions.public.require()
        def resolve_masked_string(root, info):
            return "masked string"

    schema = graphene.Schema(query=Query)
    monkeypatch.setattr("takumi.views.gql.public_schema", schema)

    query = "{publicString, maskedString}"

    result = client.query(url_for("api.graphql"), query)

    assert result.json["data"] == {"publicString": "public string", "maskedString": None}


def test_graphql_validate_query_permission_doesnt_do_anything_if_logged_in(
    private_schema, public_schema, monkeypatch
):
    monkeypatch.setattr("takumi.views.gql.schema", private_schema)
    monkeypatch.setattr("takumi.views.gql.public_schema", public_schema)
    monkeypatch.setattr("takumi.views.gql.current_user", mock.Mock(is_authenticated=True))

    with mock.patch.object(GraphQLView, "__init__", lambda *args: None):
        view = GraphQLView()

    query = "{publicString}"

    with mock.patch("takumi.views.gql.validate") as mock_validate:
        view.validate_query_authentication(query)

    assert not mock_validate.called


def test_graphql_validate_query_permission_doesnt_raise_401_if_public_query_valid(
    private_schema, public_schema, monkeypatch
):
    monkeypatch.setattr("takumi.views.gql.schema", private_schema)
    monkeypatch.setattr("takumi.views.gql.public_schema", public_schema)
    monkeypatch.setattr("takumi.views.gql.current_user", mock.Mock(is_authenticated=False))

    with mock.patch.object(GraphQLView, "__init__", lambda *args: None):
        view = GraphQLView()

    query = "{publicString}"

    with mock.patch("takumi.views.gql.validate") as mock_validate:
        view.validate_query_authentication(query)

    assert mock_validate.called


def test_graphql_validate_query_permission_does_raise_401_if_public_query_invalid_but_private_valid(
    private_schema, public_schema, monkeypatch
):
    monkeypatch.setattr("takumi.views.gql.schema", private_schema)
    monkeypatch.setattr("takumi.views.gql.public_schema", public_schema)
    monkeypatch.setattr("takumi.views.gql.current_user", mock.Mock(is_authenticated=False))

    with mock.patch.object(GraphQLView, "__init__", lambda *args: None):
        view = GraphQLView()

    query = "{privateString}"

    with pytest.raises(APIError, match="Unauthorized"):
        view.validate_query_authentication(query)


def test_graphql_validate_query_permission_doesnt_raise_401_if_public_query_invalid_and_private_invalid(
    private_schema, public_schema, monkeypatch
):
    monkeypatch.setattr("takumi.views.gql.schema", private_schema)
    monkeypatch.setattr("takumi.views.gql.public_schema", public_schema)
    monkeypatch.setattr("takumi.views.gql.current_user", mock.Mock(is_authenticated=False))

    with mock.patch.object(GraphQLView, "__init__", lambda *args: None):
        view = GraphQLView()

    query = "{invalidQuery}"

    view.validate_query_authentication(query)
