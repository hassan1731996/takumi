import datetime as dt
import json

from graphene import ObjectType

from takumi.extensions import instascrape, redis
from takumi.gql import fields
from takumi.roles import permissions


class SampleMedia(ObjectType):
    id = fields.String()
    url = fields.String()
    link = fields.String()


class MediaQuery:
    sample_medias = fields.List(SampleMedia)

    @permissions.public.require()
    def resolve_sample_medias(root, info):
        cache_key = "sample_medias"
        conn = redis.get_connection()
        result = conn.get(cache_key)

        if result is not None:
            raw_media = json.loads(result)
        else:
            raw_media = instascrape.get_user_media("takumilogo", nocache=False)
            conn.setex(
                cache_key, int(dt.timedelta(hours=24).total_seconds()), json.dumps(raw_media)
            )

        sample_medias = [
            {"id": media.get("id"), "url": media.get("url"), "link": media.get("link")}
            for media in raw_media["data"]
        ]

        return sample_medias
