import json
import re
from typing import Dict

import graphene

from takumi.gql import fields


class MaxDepth(Exception):
    pass


class QueryGenerator:

    _fields: Dict[str, str] = {}

    @classmethod  # noqa
    def extract_fields(cls, gql_type, max_depth=10, root=True):
        results = []
        for attr in dir(gql_type):
            val = getattr(gql_type, attr)

            try:
                while issubclass(type(val), graphene.List):
                    val = val.of_type()
            except Exception as e:
                if "An Interface cannot be intitialized" in str(e):
                    continue
                else:
                    raise e

            val_type = type(val)

            if not issubclass(val_type, (graphene.Field, graphene.Scalar, graphene.ObjectType)):
                continue

            while issubclass(val_type, fields.Field):
                val_type = val.type
                while issubclass(type(val_type), graphene.List):
                    val_type = val_type.of_type

            while issubclass(val_type, graphene.List):
                val_type = val.of_type

            if issubclass(val_type, graphene.types.scalars.Scalar):
                results.append(attr)
            else:
                if max_depth == 0:
                    raise MaxDepth
                try:
                    results.append(
                        {attr: cls.extract_fields(val_type, max_depth=max_depth - 1, root=False)}
                    )
                except MaxDepth as e:
                    if root:
                        # skip nested fields that go too deep down(possibly circular references)
                        continue
                    raise e
        return results

    @classmethod
    def generate_query_with_camelcase(cls, query_name, **kwargs):
        results = cls.generate_query(query_name, **kwargs)
        return re.sub("_([a-z])", lambda match: match.group(1).upper(), results)

    @classmethod
    def generate_query(cls, query_name, **kwargs):
        from takumi.gql.query import Query

        gql_type = getattr(Query, query_name).type

        if not cls._fields.get(gql_type):
            cls._fields[gql_type] = cls.extract_fields(gql_type)

        fields = cls._fields[gql_type]
        jsoned_kwargs = json.dumps(kwargs)[1:-1]

        args = re.sub(r'"(\S+)":', r"\1:", jsoned_kwargs)

        fields = (
            json.dumps(fields, sort_keys=True)
            .replace("{", "")
            .replace("}", "")
            .replace(":", "")
            .replace("[", "{")
            .replace("]", "}")
            .replace('"', "")
            .replace(",", "")
        )

        return f"{query_name}({args}) {fields}"
