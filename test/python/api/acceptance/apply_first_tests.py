import datetime as dt

import mock
import pytest

from takumi.gql.mutation.apply_first import (
    ApproveCandidate,
    MarkAsSelected,
    PromoteSelectedToAccepted,
    PromoteSelectedToCandidate,
    RejectCandidate,
)
from takumi.gql.mutation.campaign import CreateCampaign, LaunchCampaign
from takumi.gql.mutation.influencer_campaign import RequestParticipationInCampaign
from takumi.gql.mutation.post import CreatePost, UpdatePost
from takumi.gql.mutation.targeting import TargetCampaign
from takumi.gql.query.apply_first import ApplyFirstQuery
from takumi.models import Campaign, Interest
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.post import PostTypes


@pytest.fixture(autouse=True, scope="module")
def _auto_stub_permission_decorator_required_for_mutations():
    with mock.patch("flask_principal.IdentityContext.can", return_value=True):
        yield


def test_apply_first_brand_match_campaign_for_a_full_cycle(  # noqa [C901]
    monkeypatch,
    client,
    market,
    db_advertiser,
    db_session,
    db_region,
    influencer_factory,
    facebook_account_factory,
    region_factory,
    user_factory,
    update_influencer_es,
    db_developer_user,
    db_advertiser_user,
    tiger_task,
):
    monkeypatch.setattr("takumi.emails.email.Email._send_email", lambda *args: None)
    monkeypatch.setattr("takumi.models.User.email", "test@takumi.com")
    monkeypatch.setattr("takumi.gql.mutation.advertiser.current_user", db_developer_user)
    monkeypatch.setattr("takumi.gql.mutation.offer.current_user", db_developer_user)
    mock_task = mock.Mock()
    mock_task.id = "123"
    now = dt.datetime.now(dt.timezone.utc)

    # Lets create a minimal campaign.
    campaign = (
        CreateCampaign()
        .mutate(
            "info",
            db_advertiser.id,
            market.slug,
            "assets",
            units=10,
            price=10000,
            list_price=10000,
            shipping_required=False,
            pictures=["Picture"],
            prompts=[],
            has_nda=False,
            brand_safety=True,
            extended_review=False,
            owner=db_developer_user.id,
            name="test Campaign",
            description="123",
            campaign_manager=db_developer_user.id,
            secondary_campaign_manager=db_developer_user.id,
            community_manager=db_developer_user.id,
            industry=None,
            brand_match=True,
            require_insights=False,
            pro_bono=False,
        )
        .campaign
    )

    # A Post for said campaign
    CreatePost().mutate("info", campaign.id)

    post_types = [PostTypes.standard, PostTypes.video]
    for i, post in enumerate(campaign.posts):
        with mock.patch("takumi.tasks.posts.reminders.tiger"):
            UpdatePost().mutate(
                "info",
                post.id,
                post_type=post_types[i],  # TODO: Add event post as well
                opened=now + dt.timedelta(days=1),
                submission_deadline=now + dt.timedelta(days=2),
                deadline=now + dt.timedelta(days=5),
                brief=[{"type": "heading", "value": "Campaign brief"}],
            )

    # Finally we can launch our campaign!
    campaign = LaunchCampaign().mutate("info", campaign.id).campaign
    campaign.public = True

    ######################################################################
    #       Lets create some eligible influencers for our campaign       #
    ######################################################################

    targeted_interests = [Interest(name="A")]
    targeted_gender = "male"
    targeted_ages = [19, 20, 21]
    correct_birthday = now.replace(year=now.year - 19)

    influencers = []

    for i in range(0, 40):
        influencer = influencer_factory(
            state="reviewed",
            target_region=db_region,
            interests=targeted_interests,
            user=user_factory(gender=targeted_gender, birthday=correct_birthday),
        )
        influencer.user.facebook_account = facebook_account_factory(users=[influencer.user])
        influencers.append(influencer)

    db_session.add_all(influencers)
    db_session.commit()

    for influencer in influencers:
        update_influencer_es(influencer.id)

    # Lets see if these influencers can be targeted
    campaign = (
        TargetCampaign()
        .mutate(
            "info",
            campaign.id,
            regions=[db_region.id],
            gender=targeted_gender,
            ages=targeted_ages,
            interest_ids=[i.id for i in targeted_interests],
        )
        .campaign
    )

    # Make all influencers request for participation
    for influencer in influencers:
        if campaign in influencer.campaigns.with_entities(Campaign):
            offer = (
                RequestParticipationInCampaign()
                .mutate("info", campaign.id, username=influencer.username)
                .offer
            )
            assert offer.state == OFFER_STATES.REQUESTED

    offers = campaign.offers
    assert len(offers) == 40

    """ The whole process from requested to accepted is:
    1. Select 5 offers to become candidates
    2. Ask the server to select the the next suggested (10 more)
    3. Turn all selected into candidates
    4. Reject some candidates
    5. Approve the rest
    6. Select 10 offers to become accepted
    7. Accept the selected offers
    """

    # 1. Select 20 offers to become candidates
    for i in range(0, 20):
        assert offers[i].state == OFFER_STATES.REQUESTED
        assert offers[i].is_selected == False
        MarkAsSelected().mutate("info", offers[i].id)
        assert offers[i].state == OFFER_STATES.REQUESTED
        assert offers[i].is_selected == True

    # 2. Turn all selected into candidates
    PromoteSelectedToCandidate().mutate("info", campaign.id)
    for i in range(0, 20):
        assert offers[i].state == OFFER_STATES.CANDIDATE
        assert offers[i].is_selected == False
    for i in range(20, 40):
        assert offers[i].state == OFFER_STATES.REQUESTED
        assert offers[i].is_selected == False

    candidates = ApplyFirstQuery.resolve_offers_candidates("root", "info", campaign_id=campaign.id)
    assert len(list(candidates)) == 20

    # 3. Reject some candidates
    with client.user_request_context(db_advertiser_user):
        for i in [*range(0, 3), *range(10, 12)]:
            with client.user_request_context(db_advertiser_user):
                RejectCandidate().mutate("info", offers[i].id, reason="Testing")
                assert offers[i].state == OFFER_STATES.REJECTED_BY_BRAND

    rejected = ApplyFirstQuery.resolve_offers_rejected_by_brand(
        "root", "info", campaign_id=campaign.id
    )
    assert len(list(rejected)) == 5

    # 4. Approve the rest
    for i in [*range(3, 10), *range(12, 20)]:
        ApproveCandidate().mutate("info", offers[i].id)
        assert offers[i].state == OFFER_STATES.APPROVED_BY_BRAND

    approved = ApplyFirstQuery.resolve_offers_approved_by_brand(
        "root", "info", campaign_id=campaign.id, include_accepted=True
    )
    assert len(list(approved)) == 15

    # 5. Select 10 offers to become accepted
    for i in [*range(4, 6), *range(12, 20)]:
        assert offers[i].state == OFFER_STATES.APPROVED_BY_BRAND
        assert offers[i].is_selected == False
        MarkAsSelected().mutate("info", offers[i].id)
        assert offers[i].state == OFFER_STATES.APPROVED_BY_BRAND
        assert offers[i].is_selected == True

    # 6. Accept the selected offers
    PromoteSelectedToAccepted().mutate("info", campaign.id, force=False)

    # Verify all states
    for i in range(0, 3):
        assert offers[i].state == OFFER_STATES.REJECTED_BY_BRAND  # In 3.

    assert offers[3].state == OFFER_STATES.APPROVED_BY_BRAND  # In 4.

    for i in range(4, 6):
        assert offers[i].state == OFFER_STATES.ACCEPTED  # In 5.

    for i in range(6, 10):
        assert offers[i].state == OFFER_STATES.APPROVED_BY_BRAND  # In 4.

    for i in range(10, 12):
        assert offers[i].state == OFFER_STATES.REJECTED_BY_BRAND  # In 3.

    for i in range(12, 20):
        assert offers[i].state == OFFER_STATES.ACCEPTED  # In 5.
