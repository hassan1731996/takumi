import mock

from takumi.gql.types.campaign import Campaign


def test_resolve_total_creators(campaign):
    with mock.patch(
        "takumi.gql.types.campaign.CampaignService.get_number_of_accepted_influencers",
        return_value=50,
    ) as mock_get_number_of_accepted_influencers:
        total_creators = Campaign.resolve_total_creators(campaign, "info")
        assert total_creators == 50
        mock_get_number_of_accepted_influencers.assert_called_once_with([campaign.id])
