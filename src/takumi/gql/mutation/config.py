import json

from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.models import Config
from takumi.roles import permissions


class SetConfigValue(Mutation):
    """Set value of an existing config variable"""

    class Arguments:
        key = arguments.String(required=True, description="The key of the config")
        value = arguments.String(required=True, description="The value, will be json loaded")

    config = fields.Field("Config")

    @permissions.developer.require()
    def mutate(root, info, key, value):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            # Assuming it's just a string
            pass

        config = Config.get(key)
        if not config:
            raise MutationException(f"Config ({key}) not found")

        config.value = value
        db.session.commit()

        return SetConfigValue(config=config, ok=True)


class ConfigMutation:
    set_config_value = SetConfigValue.Field()
