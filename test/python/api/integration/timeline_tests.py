import datetime as dt

from freezegun import freeze_time

from takumi.models import Address, Gig, Influencer, Insight, InstagramPost, Offer, Payment, Post
from takumi.timeline import timeline_for_post
from takumi.timeline.step import Step, influencer_post_step

""" Tests are based on the old app timelines, where there was a separate
component for each timeline state. The following timelines are tested (as of
2020-06-18)

1. RequestToParticipateTimeline
2. RequestedTimeline
3. AcceptOfferTimeline <- SKIPPED: Legacy, same as 1., different title
4. MissingShippingInfoTimeline
5. AwaitingShippingTimeline
6. SubmitForApprovalTimeline
7. InReviewTimeline
8. WaitingToPostTimeline
9. PostToInstagramTimeline
10. PostedTimeline
11. SubmitInsightsTimeline
12. VerifyInsightsTimeline
13. ClaimRewardTimeline
14. ClientRejectedTimeline
15. ClaimedTimeline
16. ResubmitTimeline
"""

NOW = dt.datetime(2020, 1, 10, tzinfo=dt.timezone.utc)


@freeze_time(NOW)
def test_timeline_request_to_participate(db_post: Post, db_influencer: Influencer) -> None:
    # 1. RequestToParticipateTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.campaign.started = NOW
    db_post.opened = NOW + dt.timedelta(days=1)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_post.campaign.require_insights = True

    assert influencer_post_step(db_post, db_influencer) == Step.REQUEST_TO_PARTICIPATE

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "active"
    assert timeline[0].description is None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "active"
    assert timeline[1].description is None
    assert timeline[1].dates is not None
    assert timeline[1].dates.start == db_post.campaign.started
    assert timeline[1].dates.end == db_post.submission_deadline

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "active"
    assert timeline[2].description is None
    assert timeline[2].dates is not None
    assert timeline[2].dates.start == db_post.opened
    assert timeline[2].dates.end == db_post.deadline

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "active"
    assert timeline[3].description == "48 hours after posting"
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "active"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_requested(db_offer: Offer, db_post: Post, db_influencer: Influencer) -> None:
    # 2. RequestedTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.campaign.started = NOW
    db_post.opened = NOW + dt.timedelta(days=1)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_offer.state = Offer.STATES.REQUESTED
    db_post.campaign.require_insights = True

    assert influencer_post_step(db_post, db_influencer) == Step.REQUESTED

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "active"
    assert timeline[0].description is None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "inactive"
    assert timeline[1].description is None
    assert timeline[1].dates is not None
    assert timeline[1].dates.start == db_post.campaign.started
    assert timeline[1].dates.end == db_post.submission_deadline

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "inactive"
    assert timeline[2].description is None
    assert timeline[2].dates is not None
    assert timeline[2].dates.start == db_post.opened
    assert timeline[2].dates.end == db_post.deadline

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "inactive"
    assert timeline[3].description == "48 hours after posting"
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "inactive"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_missing_shipping_info(
    db_offer: Offer, db_post: Post, db_influencer: Influencer
) -> None:
    # 4. MissingShippingInfoTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.campaign.started = NOW
    db_post.opened = NOW + dt.timedelta(days=1)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_post.campaign.shipping_required = True
    db_post.campaign.require_insights = True
    db_offer.state = Offer.STATES.ACCEPTED

    assert influencer_post_step(db_post, db_influencer) == Step.MISSING_SHIPPING_INFO

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "active"
    assert timeline[0].description == (
        "Your shipping address is missing. "
        "Your reservation may be cancelled if you don’t add it."
    )
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "inactive"
    assert timeline[1].description is None
    assert timeline[1].dates is not None
    assert timeline[1].dates.start == db_post.campaign.started
    assert timeline[1].dates.end == db_post.submission_deadline

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "inactive"
    assert timeline[2].description is None
    assert timeline[2].dates is not None
    assert timeline[2].dates.start == db_post.opened
    assert timeline[2].dates.end == db_post.deadline

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "inactive"
    assert timeline[3].description == "48 hours after posting"
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "inactive"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_awaiting_shipping(
    db_offer: Offer, db_post: Post, db_influencer: Influencer, db_address: Address
) -> None:
    # 5. AwaitingShippingTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.campaign.started = NOW
    db_post.opened = NOW + dt.timedelta(days=1)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_post.campaign.shipping_required = True
    db_post.campaign.require_insights = True
    db_offer.state = Offer.STATES.ACCEPTED

    assert influencer_post_step(db_post, db_influencer) == Step.AWAITING_SHIPPING

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description == "Your product is waiting to be dispatched."
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "inactive"
    assert timeline[1].description is None
    assert timeline[1].dates is not None
    assert timeline[1].dates.start == db_post.campaign.started
    assert timeline[1].dates.end == db_post.submission_deadline

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "inactive"
    assert timeline[2].description is None
    assert timeline[2].dates is not None
    assert timeline[2].dates.start == db_post.opened
    assert timeline[2].dates.end == db_post.deadline

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "inactive"
    assert timeline[3].description == "48 hours after posting"
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "inactive"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_submit_for_approval(
    db_offer: Offer, db_post: Post, db_influencer: Influencer
) -> None:
    # 6. SubmitForApprovalTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.campaign.started = NOW - dt.timedelta(days=5)
    db_post.opened = NOW - dt.timedelta(days=1)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_post.campaign.require_insights = True
    db_offer.state = Offer.STATES.ACCEPTED

    assert influencer_post_step(db_post, db_influencer) == Step.SUBMIT_FOR_APPROVAL

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description == None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "active"
    assert (
        timeline[1].description
        == "This campaign requires approval of your image and caption before you post to Instagram."
    )
    assert timeline[1].dates is not None
    assert timeline[1].dates.start == db_post.campaign.started
    assert timeline[1].dates.end == db_post.submission_deadline

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "inactive"
    assert timeline[2].description is None
    assert timeline[2].dates is not None
    assert timeline[2].dates.start == db_post.opened
    assert timeline[2].dates.end == db_post.deadline

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "inactive"
    assert timeline[3].description == "48 hours after posting"
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "inactive"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_in_review(
    db_offer: Offer, db_gig: Gig, db_post: Post, db_influencer: Influencer
) -> None:
    # 7. InReviewTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.opened = NOW - dt.timedelta(days=1)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_post.campaign.require_insights = True
    db_offer.state = Offer.STATES.ACCEPTED
    db_gig.state = Gig.STATES.SUBMITTED

    assert influencer_post_step(db_post, db_influencer) == Step.IN_REVIEW

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description == None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "complete"
    assert timeline[1].description == "Your post is being reviewed."
    assert timeline[1].dates is None

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "inactive"
    assert timeline[2].description is None
    assert timeline[2].dates is not None
    assert timeline[2].dates.start == db_post.opened
    assert timeline[2].dates.end == db_post.deadline

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "inactive"
    assert timeline[3].description == "48 hours after posting"
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "inactive"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_waiting_to_post(
    db_offer: Offer, db_gig: Gig, db_post: Post, db_influencer: Influencer
) -> None:
    # 8. WaitingToPostTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.opened = NOW + dt.timedelta(days=1)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_post.campaign.require_insights = True
    db_offer.state = Offer.STATES.ACCEPTED
    db_gig.state = Gig.STATES.APPROVED

    assert influencer_post_step(db_post, db_influencer) == Step.WAITING_TO_POST

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description == None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "complete"
    assert timeline[1].description == "Your post has been approved, but it should not go live yet."
    assert timeline[1].dates is None

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "inactive"
    assert timeline[2].description is None
    assert timeline[2].dates is not None
    assert timeline[2].dates.start == db_post.opened
    assert timeline[2].dates.end == db_post.deadline

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "inactive"
    assert timeline[3].description == "48 hours after posting"
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "inactive"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_post_to_instagram(
    db_offer: Offer, db_gig: Gig, db_post: Post, db_influencer: Influencer
) -> None:
    # 9. PostToInstagramTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.opened = NOW - dt.timedelta(days=1)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_post.campaign.require_insights = True
    db_offer.state = Offer.STATES.ACCEPTED
    db_gig.state = Gig.STATES.APPROVED

    assert influencer_post_step(db_post, db_influencer) == Step.POST_TO_INSTAGRAM

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description == None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "complete"
    assert timeline[1].description is None
    assert timeline[1].dates is None

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "active"
    assert timeline[2].description is None
    assert timeline[2].dates is not None
    assert timeline[2].dates.start == db_post.opened
    assert timeline[2].dates.end == db_post.deadline

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "inactive"
    assert timeline[3].description == "48 hours after posting"
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "inactive"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_posted(
    db_offer: Offer,
    db_gig: Gig,
    db_instagram_post: InstagramPost,
    db_post: Post,
    db_influencer: Influencer,
) -> None:
    # 10. PostedTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.opened = NOW - dt.timedelta(days=1)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_offer.state = Offer.STATES.ACCEPTED
    db_gig.state = Gig.STATES.APPROVED
    db_gig.is_posted = True
    db_gig.is_posted = True
    db_gig.is_verified = True
    db_offer.campaign.require_insights = True
    db_instagram_post.posted = NOW - dt.timedelta(hours=3)

    assert influencer_post_step(db_post, db_influencer) == Step.AWAITING_INSIGHTS

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description == None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "complete"
    assert timeline[1].description is None
    assert timeline[1].dates is None

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "complete"
    assert timeline[2].description is None
    assert timeline[2].dates is None

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "inactive"
    assert timeline[3].description == "48 hours after posting"
    assert timeline[3].dates is not None
    assert timeline[3].dates.start == db_gig.end_of_review_period
    assert timeline[3].dates.end == db_gig.end_of_review_period + dt.timedelta(hours=24)

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "inactive"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_submit_insights(
    db_offer: Offer,
    db_gig: Gig,
    db_instagram_post: InstagramPost,
    db_post: Post,
    db_influencer: Influencer,
) -> None:
    # 11. SubmitInsightsTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.opened = NOW - dt.timedelta(days=5)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_offer.state = Offer.STATES.ACCEPTED
    db_gig.state = Gig.STATES.APPROVED
    db_gig.is_posted = True
    db_gig.is_verified = True
    db_offer.campaign.require_insights = True
    db_instagram_post.posted = NOW - dt.timedelta(days=3)

    assert influencer_post_step(db_post, db_influencer) == Step.SUBMIT_INSIGHTS

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description == None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "complete"
    assert timeline[1].description is None
    assert timeline[1].dates is None

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "complete"
    assert timeline[2].description is None
    assert timeline[2].dates is None

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "active"
    assert timeline[3].description is None
    assert timeline[3].dates is not None
    assert timeline[3].dates.start == db_gig.end_of_review_period
    assert timeline[3].dates.end == db_gig.end_of_review_period + dt.timedelta(hours=24)

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "inactive"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_verify_insights(
    db_offer: Offer,
    db_gig: Gig,
    db_instagram_post: InstagramPost,
    db_insight: Insight,
    db_post: Post,
    db_influencer: Influencer,
) -> None:
    # 12. VerifyInsightsTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.opened = NOW - dt.timedelta(days=5)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_offer.state = Offer.STATES.ACCEPTED
    db_gig.state = Gig.STATES.APPROVED
    db_gig.is_posted = True
    db_gig.is_verified = True
    db_offer.campaign.require_insights = True
    db_instagram_post.posted = NOW - dt.timedelta(days=3)

    assert influencer_post_step(db_post, db_influencer) == Step.VERIFY_INSIGHTS

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description == None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "complete"
    assert timeline[1].description is None
    assert timeline[1].dates is None

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "complete"
    assert timeline[2].description is None
    assert timeline[2].dates is None

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "complete"
    assert timeline[3].description == "Insights are being verified"
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "inactive"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_claim_reward(
    db_offer: Offer,
    db_gig: Gig,
    db_instagram_post: InstagramPost,
    db_insight: Insight,
    db_post: Post,
    db_influencer: Influencer,
) -> None:
    # 13. ClaimRewardTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.opened = NOW - dt.timedelta(days=5)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_offer.state = Offer.STATES.ACCEPTED
    db_gig.state = Gig.STATES.APPROVED
    db_gig.is_posted = True
    db_gig.is_verified = True
    db_offer.campaign.require_insights = True
    db_offer.is_claimable = True
    db_offer.payable = NOW + dt.timedelta(days=14)
    db_instagram_post.posted = NOW - dt.timedelta(days=3)
    db_insight.state = Insight.STATES.APPROVED

    assert influencer_post_step(db_post, db_influencer) == Step.CLAIM_REWARD

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description == None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "complete"
    assert timeline[1].description is None
    assert timeline[1].dates is None

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "complete"
    assert timeline[2].description is None
    assert timeline[2].dates is None

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "complete"
    assert timeline[3].description is None
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "active"
    assert timeline[4].dates is not None
    assert timeline[4].dates.start == db_offer.payable
    assert timeline[4].dates.end is None
    assert timeline[4].description is None


@freeze_time(NOW)
def test_timeline_client_rejected(
    db_offer: Offer,
    db_gig: Gig,
    db_instagram_post: InstagramPost,
    db_insight: Insight,
    db_post: Post,
    db_influencer: Influencer,
) -> None:
    # 14. ClientRejectedTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.opened = NOW - dt.timedelta(days=5)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_offer.state = Offer.STATES.ACCEPTED
    db_gig.state = Gig.STATES.REJECTED
    db_offer.is_claimable = False
    db_offer.campaign.require_insights = True
    db_instagram_post.posted = NOW - dt.timedelta(days=3)
    db_insight.state = Insight.STATES.APPROVED

    assert influencer_post_step(db_post, db_influencer) == Step.CLIENT_REJECTED

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description == None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "complete"
    assert timeline[1].description is None
    assert timeline[1].dates is None

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "incomplete"
    assert timeline[2].description is None
    assert timeline[2].dates is None

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "incomplete"
    assert timeline[3].description is None
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "inactive"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_client_rejected_claimable(
    db_offer: Offer,
    db_gig: Gig,
    db_instagram_post: InstagramPost,
    db_insight: Insight,
    db_post: Post,
    db_influencer: Influencer,
) -> None:
    # 14. ClientRejectedTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.opened = NOW - dt.timedelta(days=5)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_offer.state = Offer.STATES.ACCEPTED
    db_gig.state = Gig.STATES.REJECTED
    db_offer.is_claimable = True
    db_offer.campaign.require_insights = True
    db_instagram_post.posted = NOW - dt.timedelta(days=3)
    db_insight.state = Insight.STATES.APPROVED

    assert influencer_post_step(db_post, db_influencer) == Step.CLAIM_REWARD

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description == None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "complete"
    assert timeline[1].description is None
    assert timeline[1].dates is None

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "incomplete"
    assert timeline[2].description is None
    assert timeline[2].dates is None

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "incomplete"
    assert timeline[3].description is None
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "active"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_claimed(
    db_offer: Offer, db_post: Post, db_influencer: Influencer, db_session
) -> None:
    # 15. ClaimedTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.opened = NOW + dt.timedelta(days=1)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_offer.state = Offer.STATES.ACCEPTED
    db_post.campaign.require_insights = True

    payment = Payment(
        type="takumi", state="paid", successful=True, offer=db_offer, currency="gbp", amount=12345
    )
    db_session.add(payment)
    db_session.commit()

    assert influencer_post_step(db_post, db_influencer) == Step.CLAIMED

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description is None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "complete"
    assert timeline[1].description is None
    assert timeline[1].dates is None

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "complete"
    assert timeline[2].description is None
    assert timeline[2].dates is None

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "complete"
    assert timeline[3].description is None
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "complete"
    assert timeline[4].description is None
    assert timeline[4].dates is None


@freeze_time(NOW)
def test_timeline_resubmit_for_approval(
    db_offer: Offer, db_gig: Gig, db_post: Post, db_influencer: Influencer
) -> None:
    # 16. ResubmitTimeline

    db_post.campaign.public = True
    db_post.campaign.apply_first = True
    db_post.opened = NOW - dt.timedelta(days=1)
    db_post.submission_deadline = NOW + dt.timedelta(days=5)
    db_post.deadline = NOW + dt.timedelta(days=10)
    db_post.campaign.require_insights = True
    db_gig.state = Gig.STATES.REQUIRES_RESUBMIT
    db_gig.resubmit_reason = "A reason for resubmit"
    db_gig.resubmit_explanation = "Further explanation"
    db_offer.state = Offer.STATES.ACCEPTED

    assert influencer_post_step(db_post, db_influencer) == Step.RESUBMIT

    timeline = timeline_for_post(db_post, db_influencer)

    assert len(timeline) == 5

    assert timeline[0].title == "Request to Participate"
    assert timeline[0].state.value == "complete"
    assert timeline[0].description == None
    assert timeline[0].dates is None

    assert timeline[1].title == "Submit for Approval"
    assert timeline[1].state.value == "active"
    assert timeline[1].description == "A reason for resubmit\n\nFurther explanation"

    assert timeline[2].title == "Post to Instagram"
    assert timeline[2].state.value == "inactive"
    assert timeline[2].description is None
    assert timeline[2].dates is not None
    assert timeline[2].dates.start == db_post.opened
    assert timeline[2].dates.end == db_post.deadline

    assert timeline[3].title == "Submit Insights"
    assert timeline[3].state.value == "inactive"
    assert timeline[3].description == "48 hours after posting"
    assert timeline[3].dates is None

    assert timeline[4].title == "Claim Reward"
    assert timeline[4].state.value == "inactive"
    assert timeline[4].description is None
    assert timeline[4].dates is None
