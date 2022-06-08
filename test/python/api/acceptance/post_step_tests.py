import datetime as dt

from freezegun import freeze_time

from takumi.constants import WAIT_BEFORE_CLAIM_HOURS
from takumi.gql.mutation.gig import (
    ApproveGig,
    LinkGig,
    RequestGigResubmission,
    ReviewGig,
    SubmitMedia,
)
from takumi.gql.mutation.insight import RequestInsightResubmission, SubmitInsight, UpdatePostInsight
from takumi.gql.mutation.offer import AcceptOffer, MarkDispatched
from takumi.gql.utils import influencer_post_step
from takumi.models import Address
from takumi.models.campaign import STATES as CAMPAIGN_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.services import PaymentService
from takumi.tasks.scheduled import offer_claimability_reaper


@freeze_time("2020-04-15")
def test_influencer_post_step(
    client, db_session, db_influencer, db_developer_user, db_campaign, db_post, db_offer
):
    db_offer.state = OFFER_STATES.INVITED
    db_campaign.require_insights = True
    db_campaign.shipping_required = True
    db_campaign.brand_safety = True
    db_campaign.state = CAMPAIGN_STATES.LAUNCHED

    db_session.commit()

    user = db_influencer.user

    # Influencer is prompted to accept the offer
    assert influencer_post_step(db_post, db_influencer) == "ACCEPT_OFFER"

    # Offer accepted and the influencer needs to fill in their address
    with client.user_request_context(user):
        AcceptOffer().mutate("info", id=db_offer.id)

    assert influencer_post_step(db_post, db_influencer) == "MISSING_SHIPPING_INFO"

    # Influencer is awaiting shipping
    # Old legacy
    db_influencer.address = Address(
        address1="12 Grimmauld Place",
        city="London",
        postal_code="123 ABC",
        country="UK",
        modified=db_offer.created + dt.timedelta(seconds=1),
    )
    db_session.add(db_influencer.address)
    db_session.commit()

    assert influencer_post_step(db_post, db_influencer) == "AWAITING_SHIPPING"

    # Product marked as dispatched and dnfluencer needs to submit
    with client.user_request_context(db_developer_user):
        MarkDispatched().mutate("root", id=db_offer.id)

    assert influencer_post_step(db_post, db_influencer) == "SUBMIT_FOR_APPROVAL"

    # A submission is made and the gig is in review
    with client.user_request_context(user):
        SubmitMedia().mutate(
            "info",
            media=[{"url": "http://image.jpg", "type": "image"}],
            caption="The greatest gig in the world",
            post_id=db_post.id,
        )

    gig = db_offer.gigs[0]

    assert influencer_post_step(db_post, db_influencer) == "IN_REVIEW"

    # Gig requires resubmit
    with client.user_request_context(db_developer_user):
        RequestGigResubmission().mutate(
            "info", id=gig.id, send_email=False, reason="Bad influencer, BAD!"
        )

    assert influencer_post_step(db_post, db_influencer) == "RESUBMIT"

    # Influencer submits again
    with client.user_request_context(user):
        SubmitMedia().mutate(
            "info",
            media=[{"url": "http://image2.jpg", "type": "image"}],
            caption="The greatest-er gig in the world",
            post_id=db_post.id,
        )

    assert influencer_post_step(db_post, db_influencer) == "IN_REVIEW"

    # Gig is reviewed, still in review since brand safety
    with client.user_request_context(db_developer_user):
        ReviewGig().mutate("info", id=gig.id)

    assert influencer_post_step(db_post, db_influencer) == "IN_REVIEW"

    # Gig is accepted and now needs ot be posted to instagram
    with client.user_request_context(db_developer_user):
        ApproveGig().mutate("info", id=gig.id)

    assert influencer_post_step(db_post, db_influencer) == "POST_TO_INSTAGRAM"

    # Influencer posts to instagram
    with client.user_request_context(user):
        LinkGig().mutate("info", id=gig.id, shortcode="shortcode")

    gig.instagram_post.posted = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=47)
    db_session.commit()

    assert influencer_post_step(db_post, db_influencer) == "POSTED"

    # Post has been up for more than 48 hours, so time to post the insights

    gig.instagram_post.posted = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=49)
    db_session.commit()

    assert influencer_post_step(db_post, db_influencer) == "SUBMIT_INSIGHTS"

    # Submit the insights and wait for it to be verified
    with client.user_request_context(user):
        SubmitInsight().mutate("info", insight_urls=["http://insight.jpg"], gig_id=gig.id)

    assert influencer_post_step(db_post, db_influencer) == "VERIFY_INSIGHTS"

    # Request resubmit of the insights

    with client.user_request_context(db_developer_user):
        RequestInsightResubmission().mutate("info", reason="Wrong post", id=gig.insight.id)

    assert influencer_post_step(db_post, db_influencer) == "SUBMIT_INSIGHTS"

    # Submit the insights and wait for it to be verified
    with client.user_request_context(user):
        SubmitInsight().mutate("info", insight_urls=["http://insight2.jpg"], gig_id=gig.id)

    assert influencer_post_step(db_post, db_influencer) == "VERIFY_INSIGHTS"

    # Process the insights
    with client.user_request_context(db_developer_user):
        UpdatePostInsight().mutate("info", id=gig.insight.id, reach=10000, processed=True)

    # The campaign is done, just waiting until they can claim it
    assert influencer_post_step(db_post, db_influencer) == "POSTED"

    # Simulate callback too early to set claimable

    # Still just posted
    assert influencer_post_step(db_post, db_influencer) == "POSTED"

    # Posted long enough time ago now
    gig.instagram_post.posted = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
        hours=WAIT_BEFORE_CLAIM_HOURS + 1
    )
    db_session.commit()
    offer_claimability_reaper()

    # Now claimable
    assert influencer_post_step(db_post, db_influencer) == "CLAIM_REWARD"

    # Claim the reward
    # From legacy view
    payment = PaymentService.create(
        db_offer.id, data={"destination": {"type": "takumi", "value": 100}}
    )
    with PaymentService(payment) as service:
        service.request({})

    assert influencer_post_step(db_post, db_influencer) == "CLAIMED"
