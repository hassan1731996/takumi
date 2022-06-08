def test_cash_fund_is_not_reservable(cash_campaign):
    assert cash_campaign.fund.is_reservable() == False


def test_cash_fund_progress_returns_completed(cash_campaign):
    progress = cash_campaign.fund.get_progress()
    assert progress["total"] == progress["submitted"]
