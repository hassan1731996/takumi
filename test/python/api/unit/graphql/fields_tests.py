import mock
import pytest
from graphene import Schema
from graphene.test import Client
from graphene.types.objecttype import ObjectType

from takumi.gql import fields
from takumi.gql.fields import FieldException, deep_source_resolver
from takumi.gql.middlewares import AuthorizationMiddleware
from takumi.roles import permissions
from takumi.roles.needs import campaign_manager_role


def test_deep_source_resolver_object_one_level_source():
    class Obj:
        target = mock.Mock()

    obj = Obj()

    result = deep_source_resolver("target")(obj, None)

    assert result == obj.target


def test_deep_source_resolver_object_multiple_level_source():
    class Foo:
        target = mock.Mock()

    class Bar:
        foo = Foo()

    bar = Bar()

    result = deep_source_resolver("foo.target")(bar, None)

    assert result == bar.foo.target


def test_deep_source_resolver_dict_one_level_source():
    d = {"target": mock.Mock()}

    result = deep_source_resolver("target")(d, None)

    assert result == d["target"]


def test_deep_source_resolver_dict_multiple_level_source():
    foo = {"bar": {"target": mock.Mock()}}

    result = deep_source_resolver("bar.target")(foo, None)

    assert result == foo["bar"]["target"]


def test_deep_source_resolver_function():
    mock_target = mock.Mock()

    class Obj:
        def target(self):
            return mock_target

    obj = Obj()

    result = deep_source_resolver("target")(obj, None)

    assert result == mock_target


def test_deep_source_resolver_mixed():
    class Qux:
        target = mock.Mock()

    class Bar:
        baz = {"qux": Qux()}

    foo = {"bar": Bar()}

    result = deep_source_resolver("bar.baz.qux.target")(foo, None)

    assert result == foo["bar"].baz["qux"].target


def test_authenticated_field_saves_needs():
    mock_need = mock.Mock()
    mock_field_type = mock.Mock()

    field = fields.AuthenticatedField(mock_field_type, needs=mock_need)

    assert field.needs == [mock_need]


def test_authenticated_field_masks_out_field_if_missing_need(
    client, advertiser_user, campaign_manager
):
    class Type(ObjectType):
        public = fields.String()
        snake_public = fields.String()
        private = fields.AuthenticatedField(fields.String, needs=campaign_manager_role)
        snake_private = fields.AuthenticatedField(fields.String, needs=campaign_manager_role)

    class Query(ObjectType):
        test = fields.Field(Type)

        @permissions.public.require()
        def resolve_test(root, info):
            return {
                "public": "public",
                "snake_public": "public",
                "private": "private",
                "snake_private": "private",
            }

    graphql_client = Client(Schema(query=Query))
    query = """{ test { public, snakePublic, private, snakePrivate } }"""

    with client.user_request_context(advertiser_user):
        result = graphql_client.execute(query, middleware=[AuthorizationMiddleware()])

        assert result == {
            "data": {
                "test": {
                    "public": "public",
                    "snakePublic": "public",
                    "private": None,
                    "snakePrivate": None,
                }
            }
        }

    with client.user_request_context(campaign_manager):
        result = graphql_client.execute(query, middleware=[AuthorizationMiddleware()])

        assert result == {
            "data": {
                "test": {
                    "public": "public",
                    "snakePublic": "public",
                    "private": "private",
                    "snakePrivate": "private",
                }
            }
        }


def test_sortedlist_raises_on_custom_resolvers():
    with pytest.raises(FieldException, match="SortedList doesn't support a custom resolver"):
        fields.SortedList(fields.String, key=lambda: True, resolver=lambda: None)


def test_sortedlist_raises_on_providing_source():
    with pytest.raises(FieldException, match="SortedList doesn't support a custom resolver"):
        fields.SortedList(fields.String, key=lambda: True, source="field")


def test_sortedlist_sorts_field(monkeypatch):
    monkeypatch.setattr("takumi.gql.fields.retrieve_root_field", lambda *args: [1, 4, 2, 3])

    field = fields.SortedList(fields.String, key=lambda x: x)

    assert field._resolver("root", "info") == [1, 2, 3, 4]


def test_sortedlist_sorts_field_reversed(monkeypatch):
    monkeypatch.setattr("takumi.gql.fields.retrieve_root_field", lambda *args: [1, 4, 2, 3])

    field = fields.SortedList(fields.String, key=lambda x: x, reverse=True)

    assert field._resolver("root", "info") == [4, 3, 2, 1]


def test_retrieve_root_field_from_an_object():
    class Obj:
        some_property = "whoa there"

    o = Obj()
    assert fields.retrieve_root_field(o, mock.Mock(field_name="some_property")) == "whoa there"
    assert fields.retrieve_root_field(o, mock.Mock(field_name="someProperty")) == "whoa there"


def test_retrieve_root_field_from_a_dictionary():
    d = {"some_property": "whoa there"}

    assert fields.retrieve_root_field(d, mock.Mock(field_name="some_property")) == "whoa there"
    assert fields.retrieve_root_field(d, mock.Mock(field_name="someProperty")) == "whoa there"


def test_sortedlist_resolves_in_a_query(client, advertiser_user, campaign_manager):
    class Type(ObjectType):
        test_list = fields.SortedList(fields.Int, key=lambda x: x)

    class Query(ObjectType):
        test_type = fields.Field(Type)

        @permissions.public.require()
        def resolve_test_type(root, info):
            return {"test_list": [1, 5, 2, 4, 3]}

    graphql_client = Client(Schema(query=Query))
    query = """{ testType { testList } }"""

    result = graphql_client.execute(query, middleware=[AuthorizationMiddleware()])

    assert "errors" not in result
    assert result["data"]["testType"]["testList"] == [1, 2, 3, 4, 5]
