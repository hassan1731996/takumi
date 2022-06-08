from takumi.gql import fields
from takumi.models import Config
from takumi.roles import permissions


class ConfigQuery:
    configs = fields.List("Config")

    @permissions.developer.require()
    def resolve_configs(root, info):
        return Config.query.all()
