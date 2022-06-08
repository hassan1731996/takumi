import base64

from takumi import models
from takumi.gql import types
from takumi.gql.fields import ConnectionField


def test_connection_field_with_negative_limit(db_session, db_advertiser):
    assert db_session.query(models.Advertiser).count() == 1

    first = 10
    resolver = lambda *args, **kwargs: models.Advertiser.query
    connection = ConnectionField(types.Advertiser)

    after = base64.b64encode(b"arrayconnection:10")

    resolved = connection.connection_resolver(
        resolver, types.AdvertiserConnection, "root", "info", first=first, after=after
    )

    assert resolved.count == 1
    assert len(resolved.edges) == 0

    resolved = connection.connection_resolver(
        resolver, types.AdvertiserConnection, "root", "info", first=first
    )

    assert len(resolved.edges) == 1
