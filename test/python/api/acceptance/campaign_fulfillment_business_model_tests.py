import datetime as dt

import mock
import pytest
from freezegun import freeze_time

from takumi.constants import WAIT_BEFORE_CLAIM_HOURS
from takumi.gql.mutation.advertiser import CreateAdvertiser
from takumi.gql.mutation.campaign import (
    CompleteCampaign,
    CreateCampaign,
    LaunchCampaign,
    UpdateCampaign,
)
from takumi.gql.mutation.gig import (
    ApproveGig,
    DismissGigReport,
    LinkGig,
    RejectGig,
    ReportGig,
    RequestGigResubmission,
    ReviewGig,
    SubmitMedia,
)
from takumi.gql.mutation.influencer_campaign import RejectCampaign, ReserveCampaign
from takumi.gql.mutation.offer import MakeOffer, RevokeOffer
from takumi.gql.mutation.payment import RequestPayment
from takumi.gql.mutation.post import CreatePost, UpdatePost
from takumi.gql.mutation.targeting import TargetCampaign
from takumi.gql.query.influencer import InfluencerQuery
from takumi.gql.query.targeting import TargetingEstimateQuery
from takumi.models import Interest
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.post import PostTypes
from takumi.services import OfferService
from takumi.services.exceptions import (
    CampaignFullyReservedException,
    CampaignLaunchException,
    GigAlreadySubmittedException,
    GigInvalidStateException,
    InfluencerNotEligibleException,
    OfferAlreadyExistsException,
    OfferNotClaimableException,
    OfferNotRejectableException,
    OfferNotReservableException,
    ServiceException,
)


class Media:
    def __init__(self, **entries):
        self.__dict__.update(entries)


def test_campaign_business_model_for_a_full_cycle(  # noqa [C901]
    monkeypatch,
    client,
    market,
    db_session,
    db_region,
    influencer_factory,
    region_factory,
    user_factory,
    update_influencer_es,
    db_developer_user,
    db_device,
):
    monkeypatch.setattr("takumi.models.Influencer.device", db_device)
    monkeypatch.setattr("takumi.emails.email.Email._send_email", lambda *args: None)
    monkeypatch.setattr("takumi.gql.mutation.advertiser.current_user", db_developer_user)
    monkeypatch.setattr("takumi.notifications.client.tiger", mock.Mock())
    monkeypatch.setattr(
        "takumi.gql.mutation.advertiser.upload_media_to_cdn",
        lambda *args: "https://imgix.com/image.jpg",
    )
    now = dt.datetime.now(dt.timezone.utc)

    # Lets create the advertiser who owns the campaign
    advertiser = (
        CreateAdvertiser()
        .mutate("info", "MyTestAdvertiser", "profile_picture", db_region.id, "testInstagramDomain")
        .advertiser
    )

    # Lets create a minimal campaign. A lot of things need to be updated before we can launch it
    campaign = (
        CreateCampaign()
        .mutate(
            "info",
            advertiser.id,
            market.slug,
            "assets",
            units=0,
            price=10000,
            list_price=10000,
            shipping_required=False,
            require_insights=False,
            pictures=[],
            prompts=[],
            has_nda=False,
            brand_safety=True,
            extended_review=False,
            owner=db_developer_user.id,
            name=None,
            description=None,
            campaign_manager=db_developer_user.id,
            secondary_campaign_manager=db_developer_user.id,
            community_manager=db_developer_user.id,
            industry=None,
            brand_match=False,
            pro_bono=False,
        )
        .campaign
    )

    # This test is for non apply_first
    campaign.apply_first = False
    db_session.commit()

    #######################################
    # Lets launch our campaign. Spec: 1.1 #
    #######################################

    # Should fail as none of the launch requirements have been fulfilled
    with pytest.raises(CampaignLaunchException) as exc:
        LaunchCampaign().mutate("info", campaign.id)

    assert "Campaign needs a `name` in order to be launched" in exc.exconly()
    assert "Campaign needs at least one `picture` in order to be launched" in exc.exconly()

    # Lets fix all failed launch requirements
    campaign = (
        UpdateCampaign()
        .mutate(
            "info",
            campaign.id,
            name="Campaign name",
            units=10,
            pictures=["picture for campaign"],
            push_notification_message=None,
        )
        .campaign
    )
    CreatePost().mutate("info", campaign.id)

    with pytest.raises(CampaignLaunchException) as exc:
        LaunchCampaign().mutate("info", campaign.id)

    assert "Each campaign's post needs a `brief` in order to be launched" in exc.exconly()
    assert "Each campaign's post needs a `deadline` in order to be launched" in exc.exconly()
    assert "Each campaign's post needs a `submission date` in order to be launched" in exc.exconly()

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
                brief=[{"type": "heading", "value": "Post brief"}],
            )

    # Finally we can launch our campaign!
    campaign = LaunchCampaign().mutate("info", campaign.id).campaign

    # Can't launch an already launched campaign
    with pytest.raises(CampaignLaunchException) as exc:
        LaunchCampaign().mutate("info", campaign.id)

    assert (
        "Campaign has to be in draft state to be launched. Current state: {}".format(
            CAMPAIGN_STATES.LAUNCHED
        )
        in exc.exconly()
    )

    ######################################################################
    # Lets see if we can find some eligible influencers for our campaign #
    ######################################################################
    not_targeted_region = region_factory(
        name="Not the same as advertiser region", locale_code="not_ad", market_slug="outside"
    )

    db_session.add(not_targeted_region)
    db_session.commit()

    targeted_interests = [Interest(name="A"), Interest(name="B"), Interest(name="C")]
    targeted_gender = "male"
    targeted_ages = [19, 20, 21]
    correct_birthday = now.replace(year=now.year - 19)

    influencer_not_targeted_due_to_region = influencer_factory(
        state="reviewed",
        target_region=not_targeted_region,
        interests=targeted_interests,
        user=user_factory(gender=targeted_gender, birthday=correct_birthday),
    )

    influencer_not_targeted_due_to_gender = influencer_factory(
        state="reviewed",
        target_region=db_region,
        interests=targeted_interests,
        user=user_factory(gender="female", birthday=correct_birthday),
    )

    influencer_not_targeted_due_to_interests = influencer_factory(
        state="reviewed",
        target_region=db_region,
        interests=[Interest(name="D")],
        user=user_factory(gender=targeted_gender, birthday=correct_birthday),
    )

    influencer_not_targeted_due_to_age = influencer_factory(
        state="reviewed",
        target_region=db_region,
        interests=targeted_interests,
        user=user_factory(gender=targeted_gender, birthday=now),
    )

    influencer_targeted = influencer_factory(
        state="reviewed",
        target_region=db_region,
        interests=targeted_interests,
        user=user_factory(gender=targeted_gender, birthday=correct_birthday),
    )

    influencer_targeted_verified = influencer_factory(
        state="verified",
        target_region=db_region,
        interests=targeted_interests,
        user=user_factory(gender=targeted_gender, birthday=correct_birthday),
    )

    db_session.add_all(
        [
            influencer_not_targeted_due_to_region,
            influencer_not_targeted_due_to_gender,
            influencer_not_targeted_due_to_interests,
            influencer_not_targeted_due_to_age,
            influencer_targeted,
            influencer_targeted_verified,
        ]
    )
    db_session.commit()

    for influencer in [
        influencer_not_targeted_due_to_region,
        influencer_not_targeted_due_to_gender,
        influencer_not_targeted_due_to_interests,
        influencer_not_targeted_due_to_age,
        influencer_targeted,
        influencer_targeted_verified,
    ]:
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

    targeting_estimate_result = TargetingEstimateQuery().resolve_targeting_estimate(
        None,
        mock.Mock(field_name="influencerEstimate"),
        campaign.id,
        [db_region.id],
        gender=targeted_gender,
        ages=targeted_ages,
        interests=[i.id for i in targeted_interests],
    )

    assert targeting_estimate_result["verified"] == 1
    assert targeting_estimate_result["eligible"] == 2
    assert (
        targeting_estimate_result["total"] == 5
    )  # The one who is not in the region is not counted

    ###################################################################
    # Lets start inviting some influencers to our campaign. Spec: 1.2 #
    ###################################################################

    # Can't send an offer to an influencer that isn't eligible/can't be targeted
    with pytest.raises(InfluencerNotEligibleException) as exc:
        MakeOffer().mutate("info", campaign.id, influencer_not_targeted_due_to_age.id, False)

    assert "Influencer is not eligible" in exc.exconly()

    monkeypatch.setattr("takumi.gql.db.current_user", db_developer_user)
    targeting_influencers = (
        InfluencerQuery().resolve_influencers("info", eligible_for_campaign_id=campaign.id).all()
    )
    assert {influencer_targeted.id, influencer_targeted_verified.id}.issubset(
        [i.id for i in targeting_influencers]
    )

    # Make an offer to our favourite influencer
    MakeOffer().mutate("info", campaign.id, influencer_targeted.id, False)

    # Cannot make that offer twice
    with pytest.raises(OfferAlreadyExistsException) as exc:
        MakeOffer().mutate("info", campaign.id, influencer_targeted.id, False)

    assert (
        "<Influencer {}> already has an offer (<Offer {}>) for <Campaign {}>".format(
            influencer_targeted.id, influencer_targeted.offers[0].id, campaign.id
        )
        in exc.exconly()
    )

    # Fill up campaign with offers
    influencers_to_fill_campaign = []
    for i in range(20):
        influencers_to_fill_campaign.append(
            influencer_factory(
                state="reviewed",
                target_region=db_region,
                interests=targeted_interests,
                user=user_factory(gender=targeted_gender, birthday=correct_birthday),
            )
        )

    db_session.add_all(influencers_to_fill_campaign)
    db_session.commit()

    for influencer in influencers_to_fill_campaign:
        update_influencer_es(influencer.id)

    for i in influencers_to_fill_campaign:
        MakeOffer().mutate("info", campaign.id, i.id, False)

    assert len(campaign.offers) == 1 + len(
        influencers_to_fill_campaign
    )  # Original targeted influencer + fillers

    ###################################################################
    # Ohh what ever will those pesky influencers do with our offers?? #
    ###################################################################

    # Test if we can accept an offer. That offer cannot be accepted again
    with client.user_request_context(influencer_targeted.user):
        ReserveCampaign().mutate(
            "info",
            influencer_targeted.offers[0].campaign_id,
            username=influencer_targeted.username,
        )
        with pytest.raises(OfferNotReservableException):
            ReserveCampaign().mutate(
                "info",
                influencer_targeted.offers[0].campaign_id,
                username=influencer_targeted.username,
            )

    # Verify he has an accepted offer now and can still be targeted
    targeting_influencers = (
        InfluencerQuery().resolve_influencers("info", eligible_for_campaign_id=campaign.id).all()
    )
    assert influencer_targeted.id in [i.id for i in targeting_influencers]

    # Test if we can revoke an offer. That offer cannot be revoked again or be accepted
    influencer_to_revoke_offer = influencers_to_fill_campaign.pop()

    RevokeOffer().mutate("info", influencer_to_revoke_offer.offers[0].id)
    with pytest.raises(ServiceException) as exc:
        RevokeOffer().mutate("info", influencer_to_revoke_offer.offers[0].id)

    with client.user_request_context(influencer_to_revoke_offer.user):
        with pytest.raises(OfferNotReservableException):
            ReserveCampaign().mutate(
                "info",
                influencer_to_revoke_offer.offers[0].campaign_id,
                username=influencer_to_revoke_offer.username,
            )

    # Test if we can reject an offer. That offer cannot be rejected again or be accepted
    influencer_to_reject_offer = influencers_to_fill_campaign.pop()
    with client.user_request_context(influencer_to_reject_offer.user):
        RejectCampaign().mutate(
            "info",
            influencer_to_reject_offer.offers[0].campaign_id,
            username=influencer_to_reject_offer.username,
        )
        with pytest.raises(OfferNotRejectableException):
            RejectCampaign().mutate(
                "info",
                influencer_to_reject_offer.offers[0].campaign_id,
                username=influencer_to_reject_offer.username,
            )
        with pytest.raises(OfferNotReservableException):
            ReserveCampaign().mutate(
                "info",
                influencer_to_reject_offer.offers[0].campaign_id,
                username=influencer_to_reject_offer.username,
            )

    # TODO: Renew a revoked offer if allowed from Takumi Admin
    # TODO: Force reserve/accept revoked and rejected offers

    ####################################################
    # Check if campaign is fully reserved. Spec: 1.2.8 #
    ####################################################

    # Accept all other remaining offers until campaign is fully reserved
    assert campaign.is_fully_reserved() is False

    influencers_with_accepted_offers = []
    with pytest.raises(CampaignFullyReservedException):
        for index, influencer in enumerate(influencers_to_fill_campaign):
            with client.user_request_context(influencer.user):
                try:
                    ReserveCampaign().mutate(
                        "info",
                        influencer.offers[0].campaign_id,
                        username=influencer.username,
                    )
                except OfferNotReservableException:
                    influencers_with_accepted_offers = influencers_to_fill_campaign[0:index]
                    break
                except CampaignFullyReservedException as e:
                    influencers_with_accepted_offers = influencers_to_fill_campaign[0:index]
                    raise e

    assert campaign.is_fully_reserved() is True
    assert (
        len(influencers_with_accepted_offers) + 1 == campaign.units
    )  # Our targeted influencer is that one extra

    ########################################################
    # Influencers do their thing and start submitting gigs #
    ########################################################
    monkeypatch.setattr("takumi.gql.mutation.gig.current_user", influencer_targeted.user)
    for post in campaign.posts:
        SubmitMedia().mutate(
            "info", caption="#ad", post_id=post.id, media=[{"type": "image", "url": "image_url"}]
        )

    with pytest.raises(GigAlreadySubmittedException):
        SubmitMedia().mutate(
            "info",
            caption="#ad",
            post_id=campaign.posts[0].id,
            media=[{"type": "image", "url": "image_url"}],
        )

    for i in influencers_with_accepted_offers:
        monkeypatch.setattr("takumi.gql.mutation.gig.current_user", i.user)
        for post in campaign.posts:
            SubmitMedia().mutate(
                "info",
                caption="#ad",
                post_id=post.id,
                media=[{"type": "image", "url": "image_url"}],
            )

    #####################################
    # Admins start handling gig submits #
    #####################################
    # Request resubmit
    submitted_gig = influencer_targeted.offers[0].gigs[0]
    gig_to_resubmit = influencer_targeted.offers[0].gigs[1]
    RequestGigResubmission().mutate("info", gig_to_resubmit.id, send_email=True)

    # Resubmit gig
    monkeypatch.setattr("takumi.gql.mutation.gig.current_user", influencer_targeted.user)
    resubmitted_gig = (
        SubmitMedia()
        .mutate(
            "info",
            caption="#ad",
            post_id=gig_to_resubmit.post.id,
            media=[{"type": "image", "url": "image_url"}],
        )
        .gig
    )

    # Can't approve a gig that is not reviewed
    with pytest.raises(GigInvalidStateException):
        ApproveGig().mutate("info", submitted_gig.id)

    # Review all gigs
    ReviewGig().mutate("info", submitted_gig.id)
    ReviewGig().mutate("info", resubmitted_gig.id)
    for i in influencers_with_accepted_offers:
        for gig in i.offers[0].gigs:
            ReviewGig().mutate("info", gig.id)

    # Report and Dismiss report
    ReportGig().mutate("info", submitted_gig.id, "some reason")
    DismissGigReport().mutate("info", submitted_gig.id)

    # Approve all gigs
    ApproveGig().mutate("info", resubmitted_gig.id)
    for i in influencers_with_accepted_offers:
        for gig in i.offers[0].gigs:
            ApproveGig().mutate("info", gig.id)

    ########################################################################
    # Offers are claimable for all valid gigs. Pre-approval spec: Timeline #
    ########################################################################

    # Rejected gigs are claimable
    ReportGig().mutate("info", resubmitted_gig.id, "some reason")
    RejectGig().mutate("info", resubmitted_gig.id, "some reason")

    # Mocking the check for the instagram post
    monkeypatch.setattr(
        "takumi.validation.media.InstagramMediaValidator.validate",
        lambda *args, **kwargs: {
            "id": "foo",
            "type": "image",
            "created": now,
            "link": "foo",
            "url": "foo",
            "caption": "A caption with the required hashtag #ad",
        },
    )

    # Post all gigs to instagram
    LinkGig().mutate("info", submitted_gig.id, "instagram_post_id")
    LinkGig().mutate("info", resubmitted_gig.id, "instagram_post_id")
    for i in influencers_with_accepted_offers:
        for gig in i.offers[0].gigs:
            LinkGig().mutate("info", gig.id, "instagram_post_id")

    #######################################################
    # Make sure the campaign is fulfilled. Specs: 1.2.11  #
    #######################################################
    assert campaign.is_fulfilled is False

    # Cannot pay out offer until end of review period
    with pytest.raises(OfferNotClaimableException, match="Not payable yet"):
        with client.user_request_context(influencer_targeted.user):
            RequestPayment().mutate(
                "info",
                offer_id=influencer_targeted.offers[0].id,
                destination_type="iban",
                destination_value="GB123123",
            )

    # Cannot set offer to claimable due to end of review period
    with pytest.raises(OfferNotClaimableException):
        OfferService(influencer_targeted.offers[0]).set_claimable()

    # Add enough time to pass review for the gig
    with freeze_time(now + dt.timedelta(hours=WAIT_BEFORE_CLAIM_HOURS + 1)):
        # Set all offers to claimable
        for i in influencers_with_accepted_offers + [influencer_targeted]:
            with OfferService(i.offers[0]) as service:
                service.set_claimable()

    assert campaign.is_fulfilled is True

    ############################################
    # Pay out all offers and complete campaign #
    ############################################
    for i in influencers_with_accepted_offers + [influencer_targeted]:
        with client.user_request_context(i.user):
            RequestPayment().mutate(
                "info",
                offer_id=i.offers[0].id,
                destination_type="iban",
                destination_value="GB123123",
            )

    # Complete campaign
    CompleteCampaign().mutate("info", campaign.id)


#############################################
# Utility functions for tests defined below #
#############################################
@pytest.fixture(autouse=True, scope="module")
def _auto_stub_permission_decorator_required_for_mutations():
    with mock.patch("flask_principal.IdentityContext.can", return_value=True):
        yield


def _get_gig_payout_schema(influencer):
    return dict(
        full_name=influencer.user.full_name,
        bank_name="fake_bank",
        country_code=influencer.target_region.locale.territory,
        destination=dict(type="iban", value="GB..."),
    )
