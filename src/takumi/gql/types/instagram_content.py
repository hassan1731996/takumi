from graphene import Interface

from takumi import models
from takumi.gql import fields


class InstagramContentInterface(Interface):
    id = fields.UUID()

    created = fields.DateTime()
    modified = fields.DateTime()
    followers = fields.Int()
    posted = fields.DateTime()
    media = fields.Field("MediaResult")

    @classmethod
    def resolve_type(cls, instance, info):
        from takumi.gql.types import InstagramPost, InstagramStory, TiktokPost

        if isinstance(instance, models.InstagramStory):
            return InstagramStory
        if isinstance(instance, models.InstagramPost):
            return InstagramPost
        if isinstance(instance, models.TiktokPost):
            return TiktokPost

        return None
