import datetime as dt

from flask import url_for

from takumi.models.offer import STATES as OFFER_STATES


def test_get_yearly_statements_returns_correct_statements_for_default_tax_year(
    influencer_client, db_payable_offer
):
    # Arrange
    db_payable_offer.influencer.target_region = None
    db_payable_offer.state = OFFER_STATES.ACCEPTED
    db_payable_offer.is_claimable = True

    # Act
    response = influencer_client.get(url_for("api.get_influencer_statements"))

    # Assert
    assert response.status_code == 200
    assert len(response.json["years"]) == 1
    assert response.json["years"][0]["label"] == str(db_payable_offer.payable.year)
    assert response.json["years"][0]["balance"]["amount"] == db_payable_offer.reward


def test_get_yearly_statements_for_gb_influencer_before_new_tax_year(
    influencer_client, db_payable_offer
):
    # Arrange
    db_payable_offer.state = OFFER_STATES.ACCEPTED
    db_payable_offer.is_claimable = True
    db_payable_offer.payable = dt.datetime(2010, 1, 1, tzinfo=dt.timezone.utc)

    # Act
    response = influencer_client.get(url_for("api.get_influencer_statements"))

    # Assert
    assert response.status_code == 200
    assert len(response.json["years"]) == 1
    assert response.json["years"][0]["label"] == str(db_payable_offer.payable.year - 1)
    assert response.json["years"][0]["balance"]["amount"] == db_payable_offer.reward


def test_get_yearly_statements_for_gb_influencer_after_new_tax_year(
    influencer_client, db_payable_offer
):
    # Arrange
    db_payable_offer.state = OFFER_STATES.ACCEPTED
    db_payable_offer.is_claimable = True
    db_payable_offer.payable = dt.datetime(2010, 6, 6, tzinfo=dt.timezone.utc)

    # Act
    response = influencer_client.get(url_for("api.get_influencer_statements"))

    # Assert
    assert response.status_code == 200
    assert len(response.json["years"]) == 1
    assert response.json["years"][0]["label"] == str(db_payable_offer.payable.year)
    assert response.json["years"][0]["balance"]["amount"] == db_payable_offer.reward
