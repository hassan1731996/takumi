import mock

from takumi.gql.query.offer import OfferQuery


def test_get_top_offers_in_campaign(offer):
    with mock.patch(
        "takumi.gql.query.offer.OfferService.get_top_offers_in_campaign", return_value=[offer]
    ) as mock_request:
        response = OfferQuery().resolve_top_offers_in_campaign("info", offer.campaign.id)

    mock_request.assert_called_once_with(offer.campaign.id)
    assert offer in response
