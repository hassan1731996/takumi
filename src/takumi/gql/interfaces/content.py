from unicodedata import normalize

from graphene import Interface
from itp import itp

from takumi.gql import fields


class ContentInterface(Interface):
    created = fields.DateTime()
    caption = fields.String()
    media = fields.Field("MediaResult")

    mentions = fields.List(fields.String, description="The mentions in the caption")
    hashtags = fields.List(fields.String, description="The hashtags in the caption")

    def resolve_media(content, info):
        if len(content.media) > 1 or len(content.media) == 0:
            return content.media

        return content.media[0]

    def resolve_mentions(content, info):
        if content.caption:
            parsed = itp.Parser().parse(normalize("NFC", content.caption))
            return parsed.users
        return []

    def resolve_hashtags(content, info):
        if content.caption:
            parsed = itp.Parser().parse(normalize("NFC", content.caption))
            return parsed.tags
        return []
