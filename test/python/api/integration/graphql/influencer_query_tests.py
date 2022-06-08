import mock
import pytest

from takumi.constants import ALL_SUPPORTED_REGIONS
from takumi.gql.query import InfluencerQuery
from takumi.gql.schema import schema
from takumi.models import Region
from takumi.search.influencer import update_influencer_info


def _get_inf_id(num):
    return "00000000-0000-4000-0000-{0:012d}".format(num)


def _get_ig_id(num):
    return "10000000-0000-4000-0000-{0:012d}".format(num)


def _get_region_id(num):
    return "20000000-0000-4000-0000-{0:012d}".format(num)


@pytest.fixture(autouse=True)
def disable_instagram_refresh():
    with mock.patch("takumi.gql.query.influencer.refresh_on_interval"):
        yield


@pytest.fixture(autouse=True)
def setup_influencers(
    db_session,
    market,
    audit_factory,
    influencer_factory,
    instagram_account_factory,
    tiger_task,
    elasticsearch,
):
    """Prepare influencers for this test suite

    There will be a total of 5 influencers

    *** Regions
        2 will be in a "city" region (subregion of "country")
        2 will be in a "country" region (4 including the city subregion)
        1 will be in an unsupported region

    *** States
        1 will be new
        3 will be reviwed
        1 will be verified
    """
    regions = [
        Region(id=_get_region_id(0), name="country", supported=True, market_slug=market.slug),
        Region(
            id=_get_region_id(1),
            path=[_get_region_id(0)],
            name="city",
            supported=True,
            market_slug=market.slug,
        ),
        Region(id=_get_region_id(2), name="unsupported", supported=False, market_slug=market.slug),
    ]
    db_session.add_all(regions)
    db_session.commit()

    influencers = (
        ("foo", 0, "new", 0, 1000),
        ("bar", 1, "reviewed", 0, 1000),
        ("baz", 2, "reviewed", 1, 1000),
        ("qux", 3, "reviewed", 2, 1000),
        ("norf", 4, "verified", 1, 1000),
        ("ineligible", 5, "new", 2, 500),
    )

    for username, num, state, region, followers in influencers:
        ig_account = instagram_account_factory(
            ig_username=username, ig_user_id=num, ig_media_id=num, token=num, followers=followers
        )
        db_session.add(ig_account)
        influencer = influencer_factory(
            instagram_account=ig_account, state=state, target_region=regions[region]
        )
        audit = audit_factory(influencer=influencer)
        db_session.add(audit)
        db_session.add(influencer)
    db_session.commit()
    tiger_task.run_tasks([update_influencer_info])
    elasticsearch.indices.refresh()


def test_resolve_influencers_no_filter(client, developer_user, db_session):
    with client.user_request_context(developer_user):
        result = InfluencerQuery().resolve_influencers(None)
        assert result.count() == 6


def test_resolve_influencers_filter_by_region(client, developer_user, db_session):
    with client.user_request_context(developer_user):
        # Country
        result = InfluencerQuery().resolve_influencers(None, region_id=_get_region_id(0))
        assert result.count() == 4

        # City
        result = InfluencerQuery().resolve_influencers(None, region_id=_get_region_id(1))
        assert result.count() == 2

        result = InfluencerQuery().resolve_influencers(None, region_id=_get_region_id(2))
        assert result.count() == 2


def test_resolve_influencers_filter_by_state(client, developer_user, db_session):
    with client.user_request_context(developer_user):
        result = InfluencerQuery().resolve_influencers(None, state=["new"])
        assert result.count() == 2

        result = InfluencerQuery().resolve_influencers(None, state=["reviewed"])
        assert result.count() == 3

        result = InfluencerQuery().resolve_influencers(None, state=["verified"])
        assert result.count() == 1


def test_resolve_influencers_filter_by_supported_region(client, developer_user, db_session):
    with client.user_request_context(developer_user):
        result = InfluencerQuery().resolve_influencers(None, region_id=ALL_SUPPORTED_REGIONS)
        assert result.count() == 4


def test_resolve_influencers_filter_by_search(client, developer_user, db_session):
    with client.user_request_context(developer_user):
        result = InfluencerQuery().resolve_influencers(None, search="qux")
        assert result.count() == 1
        assert result.first().username == "qux"

        result = InfluencerQuery().resolve_influencers(None, search="ba")
        assert result.count() == 2

        result = InfluencerQuery().resolve_influencers(None, search="xxx")
        assert result.count() == 0


def test_resolve_influencers_filter_by_eligible(client, developer_user):
    with client.user_request_context(developer_user):
        result = InfluencerQuery().resolve_influencers(None, eligible=True)
        assert result.count() == 5


def test_execute_influencer_query_by_username(client, developer_user, db_session):
    query = """query InfluencerByUsernameQuery {
        influencer(username: "%s") {
            id
        }
    }"""
    with client.user_request_context(developer_user):
        result = schema.execute(query % ("qux",))
    assert result.errors is None
    assert len(result.data["influencer"]) == 1


def test_execute_influencer_search_query(client, developer_user, db_session):
    query = """query AdminInfluencersQuery {
        influencers(search: "%s") {
            edges {
                node {
                    id
                    username
                }
            }
        }
    }
    """
    with client.user_request_context(developer_user):
        result = schema.execute(query % ("qux",))
    assert result.errors is None
    assert len(result.data.get("influencers", {}).get("edges", {})) == 1

    influencer = result.data["influencers"]["edges"][0]["node"]

    assert influencer["username"] == "qux"


def test_execute_influencer_statistics_query(client, developer_user, db_session, db_audit):
    query = """query AdminInfluencersQuery {
        influencerStats(search:"foo") {
              count
          }
    }
    """
    with client.user_request_context(developer_user):
        result = schema.execute(query)
    assert result.errors is None
    assert len(result.data) == 1
