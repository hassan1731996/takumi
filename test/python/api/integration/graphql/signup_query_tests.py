import datetime as dt

import pytest

from takumi.gql.query import SignupsQuery
from takumi.models.influencer import STATES as INFLUENCER_STATES


@pytest.fixture
def new_signup(db_session, influencer, update_influencer_es):
    influencer.state = INFLUENCER_STATES.NEW
    influencer.user.last_login = dt.datetime.now(dt.timezone.utc)
    db_session.add(influencer)
    db_session.commit()
    update_influencer_es(influencer.id)
    yield influencer


def test_resolve_influencer_signups_all_supported_regions(
    db_session, client, developer_user, new_signup
):
    with client.user_request_context(developer_user):
        result = SignupsQuery().resolve_influencer_signups(None)
        assert result["count"] == 1
        assert result["next"] == new_signup.id


def test_resolve_influencer_signups_influencer_in_unsupported_region(
    client, developer_user, new_signup, update_influencer_es
):
    new_signup.target_region.supported = False
    update_influencer_es(new_signup.id)
    with client.user_request_context(developer_user):
        result = SignupsQuery().resolve_influencer_signups(None)
        assert result["count"] == 0


def test_resolve_influencer_signups_in_supported_parent_region(
    db_session, client, developer_user, new_signup, region_factory, update_influencer_es
):
    not_directly_supported_sub_region = region_factory(
        name="Sublandia",
        supported=False,
        path=[new_signup.target_region.id],
        market_slug=new_signup.target_region.market_slug,
    )
    db_session.add(not_directly_supported_sub_region)
    db_session.commit()
    new_signup.target_region = not_directly_supported_sub_region
    update_influencer_es(new_signup.id)
    with client.user_request_context(developer_user):
        result = SignupsQuery().resolve_influencer_signups(None)
        assert result["count"] == 1
