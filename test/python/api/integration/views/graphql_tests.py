from flask import url_for


def test_post_http_influencer_query(client, developer_user, db_session, db_influencer):
    query = """query getInfluencer($id: UUIDString) {
        influencer(id: $id, refresh: false) {
            id
        }
    }
    """
    with client.use(developer_user):
        result = client.query(url_for("api.graphql"), query, {"id": db_influencer.id})
        assert "errors" not in result.json
        assert result.json["data"]["influencer"]["id"] == db_influencer.id


def test_post_http_influencer_query_with_cost(client, developer_user, db_session, db_influencer):
    query = """query getInfluencer($id: UUIDString) {
        influencer(id: $id, refresh: false) {
            id
        }
    }
    """
    with client.use(developer_user):
        result = client.query(
            url_for("api.graphql", cost=1),
            query,
            {"id": db_influencer.id},
            operation="getInfluencer",
        )
        assert "errors" not in result.json
        assert "cost" in result.json


def test_post_http_influencer_query_cost_headers(
    client, developer_user, campaign_manager, db_session, db_influencer
):
    query = """query getInfluencer($id: UUIDString) {
        influencer(id: $id, refresh: false) {
            id
        }
    }
    """
    with client.use(developer_user):
        result = client.query(
            url_for("api.graphql"), query, {"id": db_influencer.id}, operation="getInfluencer"
        )
        assert "errors" not in result.json
        assert "X-Takumi-Cost-GraphQL-getInfluencer-SQL-Queries" in result.headers

    with client.use(campaign_manager):
        result = client.query(
            url_for("api.graphql"), query, {"id": db_influencer.id}, operation="getInfluencer"
        )
        assert "errors" not in result.json
        assert "X-Takumi-Cost-GraphQL-getInfluencer-SQL-Queries" not in result.headers


def test_graphql_flask_view_emits_aggregate_statsd_metrics(
    client, developer_user, app, mock_statsd
):
    query = """query RequiresPermissionQuery($permission: String!) {
      hasPermission(permission: $permission)
    }
    """
    with client.use(developer_user):
        result = client.query(
            url_for("api.graphql"),
            query,
            {"permission": "something"},
            operation="RequiresPermissionQuery",
        )
        assert "errors" not in result.json

    assert mock_statsd.timing.called
    timing_calls = [(call[0][0], call[1]) for call in mock_statsd.timing.call_args_list]
    assert ("takumi.gql.request", {"tags": ["operation:RequiresPermissionQuery"]}) in timing_calls
    assert (
        "takumi.gql.request.cpu",
        {"tags": ["operation:RequiresPermissionQuery"]},
    ) in timing_calls
