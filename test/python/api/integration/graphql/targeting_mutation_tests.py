import pytest

from takumi.gql.mutation.targeting import TargetCampaign
from takumi.services.exceptions import ServiceException


def test_target_campaign_min_followers(client, db_developer_user, db_session, db_campaign):
    targeting = db_campaign.targeting
    assert targeting.min_followers is None

    with client.user_request_context(db_developer_user):
        TargetCampaign().mutate("info", id=db_campaign.id, min_followers=25_000)

    assert db_campaign.targeting.min_followers == 25_000

    with client.user_request_context(db_developer_user):
        TargetCampaign().mutate(
            "info", id=db_campaign.id, min_followers=targeting.absolute_min_followers
        )

    assert db_campaign.targeting.min_followers == targeting.absolute_min_followers

    with client.user_request_context(db_developer_user):
        TargetCampaign().mutate("info", id=db_campaign.id, min_followers=-1)

    assert db_campaign.targeting.min_followers == None

    with pytest.raises(
        ServiceException,
        match=f"Minimum followers can't be below {targeting.absolute_min_followers}",
    ):
        with client.user_request_context(db_developer_user):
            TargetCampaign().mutate(
                "info", id=db_campaign.id, min_followers=targeting.absolute_min_followers - 1
            )


def test_target_campaign_max_followers(client, db_developer_user, db_session, db_campaign):
    targeting = db_campaign.targeting
    assert targeting.max_followers is None

    with client.user_request_context(db_developer_user):
        TargetCampaign().mutate("info", id=db_campaign.id, max_followers=100_000)

    assert db_campaign.targeting.max_followers == 100_000

    with client.user_request_context(db_developer_user):
        TargetCampaign().mutate("info", id=db_campaign.id, max_followers=-1)

    assert db_campaign.targeting.max_followers == None

    with pytest.raises(ServiceException, match="Maximum followers can't be below 1000"):
        with client.user_request_context(db_developer_user):
            TargetCampaign().mutate(
                "info", id=db_campaign.id, max_followers=targeting.absolute_min_followers - 1
            )
