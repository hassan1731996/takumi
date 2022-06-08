import mock

from takumi.campaigns import campaign_reserve_state


@mock.patch("takumi.campaigns.db.session")
def test_reserve_state_ctx_reserved_reserved(mock_session, app, campaign):
    with mock.patch("takumi.models.campaign.Campaign.is_fully_reserved") as m:
        m.side_effect = [True, True]
        with mock.patch("takumi.campaigns.CampaignLog.add_event") as m:
            with campaign_reserve_state(campaign):
                pass
    assert not m.called


@mock.patch("takumi.campaigns.db.session")
def test_reserve_state_ctx_unreserved_reserved(mock_session, app, campaign):
    with mock.patch("takumi.funds.assets.AssetsFund.is_reservable") as m:
        m.side_effect = [True, False]
        with mock.patch("takumi.campaigns.CampaignLog.add_event") as m:
            with campaign_reserve_state(campaign):
                pass
    m.assert_called_with("full")


@mock.patch("takumi.campaigns.db.session")
def test_reserve_state_ctx_reserved_unreserved(mock_session, app, campaign):
    with mock.patch("takumi.funds.assets.AssetsFund.is_reservable") as m:
        m.side_effect = [False, True]
        with mock.patch("takumi.campaigns.CampaignLog.add_event") as m:
            with campaign_reserve_state(campaign):
                pass
    m.assert_called_with("not_full")


@mock.patch("takumi.campaigns.db.session")
def test_reserve_state_ctx_unreserved_unreserved(mock_session, app, campaign):
    with mock.patch("takumi.funds.assets.AssetsFund.is_reservable") as m:
        m.side_effect = [True, True]
        with mock.patch("takumi.campaigns.CampaignLog.add_event") as m:
            with campaign_reserve_state(campaign):
                pass
    assert not m.called
