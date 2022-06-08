import base64
import inspect
from functools import partial

import graphene
from flask_login import current_user
from graphene import relay
from graphene.relay.connection import PageInfo
from graphene.types.generic import GenericScalar as GenericScalarType
from graphene.utils.str_converters import to_camel_case, to_snake_case
from graphql_relay.connection.arrayconnection import connection_from_list_slice

from takumi.gql.exceptions import FieldException
from takumi.roles.needs import (
    advertiser_admin_access,
    advertiser_member_access,
    advertiser_owner_access,
    advertiser_role,
    manage_influencers,
    view_influencer_info,
)


def retrieve_root_field(root, info):
    """Try to retrieve the field directly from the root object, both with and without camel case"""
    try:
        names = [to_camel_case(info.field_name), to_snake_case(info.field_name)]
    except AttributeError:
        return
    for name in names:
        if isinstance(root, dict):
            if name in root:
                return root[name]
        else:
            if hasattr(root, name):
                return getattr(root, name)


def deep_source_resolver(source):
    def _deep_source_resolver(source, root, info, **kwargs):
        """Try to resolve the source from the root dynamically

        Tries to handle both nested dict and nested objects
        """
        from takumi.search.influencer.indexing import InfluencerInfo

        if isinstance(root, InfluencerInfo):
            # InfluencerInfo is a result from elasticsearch, the sources have
            # already been resolved, so simply use the root field based on the
            # graphql info
            return retrieve_root_field(root, info)

        items = source.split(".")
        result = root
        for item in items:
            if result is None:
                return None

            if isinstance(result, dict):
                result = result.get(item, None)
            else:
                result = getattr(result, item, None)

        if inspect.isfunction(result) or inspect.ismethod(result):
            return result()
        return result

    return partial(_deep_source_resolver, source)


def get_type(_type):
    if isinstance(_type, str):
        from takumi.gql import types

        try:
            result = getattr(types, _type)
        except AttributeError:
            raise ImportError(f"takumi.graqphl.types does not expose '{_type}' type")
        if not inspect.isclass(result):
            raise ImportError(f"'{result}' is not a class")
        if (
            not issubclass(result, graphene.ObjectType)
            and not issubclass(result, graphene.Union)
            and not issubclass(result, graphene.Interface)
        ):
            raise ImportError(
                "'{}' is not a subclass of graphene.ObjectType or graphene.Union or graphene.Interface".format(
                    result
                )
            )
        return result
    if inspect.isfunction(_type) or isinstance(_type, partial):
        return _type()
    return _type


def resolve_field_value(field, root, info):
    type_map = info.schema.get_type_map()
    resolver = type_map.get_resolver_for_type(info.parent_type.graphene_type, field, None)
    return resolver(root, {})


# *******
# Scalars
# *******

Boolean: graphene.Boolean = graphene.Boolean
Enum: graphene.Enum = graphene.Enum
Float: graphene.Float = graphene.Float
GenericScalar: GenericScalarType = GenericScalarType
ID: graphene.ID = graphene.ID
Int: graphene.Int = graphene.Int
String: graphene.String = graphene.String
UUID: graphene.UUID = graphene.UUID


class DateTime(graphene.DateTime):
    class Meta:
        name = "DateTime_"

    @staticmethod
    def serialize(dt):
        if isinstance(dt, str):
            value = graphene.DateTime.parse_value(dt)
        else:
            value = dt
        return graphene.DateTime.serialize(value)


class Date(graphene.Date):
    class Meta:
        name = "Date_"

    @staticmethod
    def serialize(dt):
        if isinstance(dt, str):
            value = graphene.Date.parse_value(dt)
        else:
            value = dt
        return graphene.Date.serialize(value)


# ******
# Fields
# ******


class Field(graphene.Field):
    def __init__(self, *args, **kwargs) -> None:
        if kwargs.get("required"):
            args = (graphene.NonNull(get_type(args[0])), *args[1:])
            kwargs["required"] = False
        super().__init__(*args, **kwargs)

    @property
    def type(self):
        return get_type(self._type)


class AuthenticatedField(Field):
    def __init__(self, *args, **kwargs):
        """A field that masks out the value if user doesn't have permission

        The field can provide more than one permission for the field, only one
        of the provided permissions needs to be allowed for the user to see the
        value
        """
        needs = kwargs.pop("needs", None)
        if needs is None:
            raise FieldException("AuthenticatedField missing needs")

        if type(needs) != list:
            needs = [needs]

        self.needs = needs

        role_description = f"\n\nRequires one of needs: {needs}"
        kwargs["description"] = (kwargs.get("description", "") + role_description).strip()

        super().__init__(*args, **kwargs)


# Fields that require specific needs
class ManageInfluencersField(AuthenticatedField):
    def __init__(self, *args, **kwargs):
        self.allow_self = kwargs.pop("allow_self", False)
        kwargs["needs"] = manage_influencers
        super().__init__(*args, **kwargs)

    def bypass_needs(self, influencer):
        from takumi.models import Influencer

        if not isinstance(influencer, Influencer):
            if hasattr(influencer, "influencer"):
                influencer = influencer.influencer
            else:
                return False

        if self.allow_self:
            return influencer == current_user.influencer

        return False


class ViewInfluencerInfoField(AuthenticatedField):
    def __init__(self, *args, **kwargs):
        self.allow_self = kwargs.pop("allow_self", False)
        kwargs["needs"] = view_influencer_info
        super().__init__(*args, **kwargs)

    def bypass_needs(self, influencer):
        from takumi.models import Influencer

        if not isinstance(influencer, Influencer):
            if hasattr(influencer, "influencer"):
                influencer = influencer.influencer
            else:
                return False

        if self.allow_self:
            return influencer == current_user.influencer

        return False


class AdvertiserField(AuthenticatedField):
    """A field that requires access to an advertiser"""

    def __init__(self, *args, **kwargs):
        kwargs["needs"] = [
            advertiser_admin_access,
            advertiser_member_access,
            advertiser_owner_access,
            advertiser_role,
        ]
        super().__init__(*args, **kwargs)


# *****
# Other
# *****


class List(graphene.List):
    @property
    def of_type(self):
        return get_type(self._of_type)


def _resolve_sorted(root, info, key, reverse=False, **kwargs):
    field = retrieve_root_field(root, info)

    if field is None:
        return None

    return sorted(field, key=key, reverse=reverse)


class SortedList(graphene.List):
    def __init__(self, *args, **kwargs):
        if "source" in kwargs or "resolver" in kwargs:
            raise FieldException("SortedList doesn't support a custom resolver")

        if "key" not in kwargs:
            raise FieldException("key argument is required for sorted lists")

        self._resolver = partial(
            _resolve_sorted, key=kwargs.pop("key"), reverse=kwargs.pop("reverse", False)
        )
        kwargs["resolver"] = self._resolver

        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"Sorted([{self.of_type}])"

    def __eq__(self, other):
        return isinstance(other, SortedList) and (
            self.of_type == other.of_type
            and self.args == other.args
            and self.kwargs == other.kwargs
        )


# *****
# Relay
# *****


class ConnectionField(relay.ConnectionField):
    def __init__(self, type, *args, **kwargs):
        # Allow setting the max first for a connection field, defaulting to 100
        self._max_first = kwargs.pop("_max_first", 100)
        kwargs.setdefault("all_results", Boolean())
        super().__init__(type, *args, **kwargs)

    @property
    def type(self):
        return get_type(self._type)

    def connection_resolver(self, resolver, connection, root, info, **args):
        if not args.pop("all_results", False):
            args["first"] = args.get("first", self._max_first)

        # Ignore the four base args in the resolver, they're used in the slicing below
        resolver_args = {
            key: args[key] for key in args if key not in ["first", "last", "before", "after"]
        }
        iterable = resolver(root, info, **resolver_args)
        if iterable is None:
            iterable = []
        if type(iterable) == list:
            _len = len(iterable)
        else:
            _len = iterable.count()

        if "after" in args:
            # Check if we're requesting "after" the total length of the
            # iterable. If we are, we clamp the after value down to the end of
            # the iterable so that the slice is empty
            decoded = base64.b64decode(args["after"]).decode()
            after_type, after_count = decoded.split(":", 1)

            if int(after_count) > _len:
                # Set the after value to length - 1, to request after the final index
                cursor = "{}:{}".format(after_type, _len - 1)
                encoded = base64.b64encode(cursor.encode()).decode()
                args["after"] = str(encoded)

        connection = connection_from_list_slice(
            iterable,
            args,
            slice_start=0,
            list_length=_len,
            list_slice_length=_len,
            connection_type=connection,
            pageinfo_type=PageInfo,
            edge_type=connection.Edge,
        )
        connection.iterable = iterable
        connection.count = _len
        return connection

    def get_resolver(self, parent_resolver):
        return partial(self.connection_resolver, parent_resolver, self.type)


class InfluencerConnectionField(ConnectionField):
    def connection_resolver(self, resolver, connection, root, info, **args):
        connection = super().connection_resolver(resolver, connection, root, info, **args)
        aggregations = connection.iterable.aggregations() or {}
        count_by_fields = [
            k[len("count_by_") :] for k in aggregations.keys() if k.startswith("count_by_")
        ]
        connection.count_by = []
        for field in count_by_fields:
            count_by = aggregations.get("count_by_" + field, {})
            count_by_buckets = count_by.get("buckets") or count_by.get("sub_bucket", {}).get(
                "buckets"
            )
            if count_by_buckets:
                connection.count_by.append(
                    dict(
                        field=field,
                        results=[
                            dict(
                                key=b.get("key_as_string") or b["key"],
                                followers=(
                                    b.get("sum_followers", {}).get("value", 0)
                                    or (
                                        b.get("sub_bucket", {})
                                        .get("sum_followers", {})
                                        .get("value", 0)
                                    )
                                ),
                                count=b["doc_count"],
                            )
                            for b in count_by_buckets
                        ],
                    )
                )
        return connection
