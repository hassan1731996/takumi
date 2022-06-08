import mock

from takumi.gql.mutation.location import UpdateLocation


def test_update_location_reduces_precision_to_two(app, client, influencer, influencer_user):
    with mock.patch(
        "takumi.gql.mutation.location.update_influencer_location_with_coordinates"
    ) as mock_update:
        with client.user_request_context(influencer_user):
            UpdateLocation().mutate("info", lat=12.345611, lon=65.432111)

    mock_update.assert_called_with(influencer_user.influencer, lat=12.35, lon=65.43)
