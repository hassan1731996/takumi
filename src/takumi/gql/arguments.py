import graphene
import validators
from graphene import DateTime, Enum
from graphql.language.ast import StringValue

from takumi.gql.exceptions import InvalidUrlException


class String(graphene.String):
    def __new__(self, *args, **kwargs):
        if kwargs.pop("strip", False):
            return StrippedString(*args, **kwargs)
        return graphene.String(*args, **kwargs)


class StrippedString(graphene.String):
    @classmethod
    def parse_literal(cls, node):
        return super().parse_literal(node).strip()


class Url(graphene.Scalar):
    @staticmethod
    def parse_validated_url(value):
        if not validators.url(value):
            raise InvalidUrlException(f"Invalid url: {value}")
        return str(value)

    serialize = parse_validated_url
    parse_value = parse_validated_url

    @staticmethod
    def parse_literal(ast):
        if isinstance(ast, StringValue):
            return ast.value


class UUID(graphene.UUID):
    class Meta:
        name = "UUIDString"

    @classmethod
    def parse_literal(cls, node):
        value = super().parse_literal(node)
        return str(value)

    @classmethod
    def parse_value(cls, value):
        value = super().parse_value(value)
        return str(value)


class SortOrder(Enum):
    asc = "asc"
    desc = "desc"


class PictureInput(graphene.InputObjectType):
    url = Url(required=True)


DateTime = DateTime
Date = graphene.Date
Boolean = graphene.Boolean
Field = graphene.Field
Float = graphene.Float
Int = graphene.Int
List = graphene.List
InputObjectType = graphene.InputObjectType
Enum = Enum
