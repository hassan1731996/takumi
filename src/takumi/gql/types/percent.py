from graphene import ObjectType

from takumi.gql import fields


class Percent(ObjectType):
    value = fields.Float()
    formatted_value = fields.String()

    def resolve_value(root, *args, **kwargs):
        if getattr(root, "value", None) is not None:
            root = root.value
        elif isinstance(root, dict) and root.get("value") is not None:
            root = root["value"]
        return root

    def resolve_formatted_value(root, *args, **kwargs):
        if getattr(root, "value", None) is not None:
            root = root.value
        elif isinstance(root, dict) and root.get("value") is not None:
            root = root["value"]
        return "{:.2f}%".format(root * 100)
