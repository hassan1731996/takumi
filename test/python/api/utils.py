import datetime as dt
from functools import wraps

from core.testing.factories import (
    AdvertiserConfigFactory,
    AdvertiserFactory,
    AdvertiserIndustryFactory,
    AuditFactory,
    CampaignFactory,
    CampaignMetricFactory,
    DeviceFactory,
    EmailLoginFactory,
    FacebookAccountFactory,
    GigFactory,
    InfluencerFactory,
    InstagramAccountFactory,
    InstagramPostFactory,
    InstagramStoryFactory,
    OfferEventFactory,
    OfferFactory,
    PaymentFactory,
    PostFactory,
    RegionFactory,
    StoryFrameFactory,
    SubmissionFactory,
    UserAdvertiserAssociationFactory,
    UserFactory,
)

from takumi.events.gig import GigLog
from takumi.models import (
    Address,
    Device,
    EmailLogin,
    FacebookAccount,
    Image,
    InfluencerEvent,
    InfluencerProspect,
    Insight,
    InstagramPost,
    InstagramPostComment,
    InstagramPostInsight,
    InstagramStoryFrameInsight,
    Interest,
    Targeting,
    TaxForm,
    Video,
)
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.user_advertiser_association import create_user_advertiser_association
from takumi.utils import uuid4_str


def passthrough_decorator(*args, **kwargs):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# ---- Object factories ---

_advertiser_factory = AdvertiserFactory()
_user_advertiser_association_factory = UserAdvertiserAssociationFactory()
_advertiser_config_factory = AdvertiserConfigFactory()
_advertiser_industry_factory = AdvertiserIndustryFactory()
_audit_factory = AuditFactory()
_campaign_factory = CampaignFactory()
_campaign_metric_factory = CampaignMetricFactory()
_device_factory = DeviceFactory()
_email_login_factory = EmailLoginFactory()
_facebook_account_factory = FacebookAccountFactory()
_gig_factory = GigFactory()
_influencer_factory = InfluencerFactory()
_instagram_account_factory = InstagramAccountFactory()
_instagram_post_factory = InstagramPostFactory()
_instagram_story_factory = InstagramStoryFactory()
_offer_event_factory = OfferEventFactory()
_offer_factory = OfferFactory()
_payment_factory = PaymentFactory()
_post_factory = PostFactory()
_region_factory = RegionFactory()
_story_frame_factory = StoryFrameFactory()
_submission_factory = SubmissionFactory()
_user_factory = UserFactory()


# ---- Object generators ----


def _influencer(user, region, instagram_account=None):
    return _influencer_factory(user=user, target_region=region, instagram_account=instagram_account)


def _influencer_prospect():
    return InfluencerProspect(ig_username="takumi_stone2", ig_user_id="2934947663", type="recruit")


def _prewarmed_influencer(instagram_account):
    instagram_account.verified = False
    return _influencer_factory(instagram_account=instagram_account, state="new")


def _reviewed_influencer(user, region, instagram_account=None):
    return _influencer_factory(
        user=user, target_region=region, instagram_account=instagram_account, state="reviewed"
    )


def _verified_influencer(user, region, instagram_account=None, interests=None):
    if interests is None:
        interests = []
    return _influencer_factory(
        user=user,
        target_region=region,
        instagram_account=instagram_account,
        state="verified",
        interests=interests,
    )


def _disabled_influencer(user, region, instagram_account=None):
    return _influencer_factory(
        user=user,
        target_region=region,
        instagram_account=instagram_account,
        state="disabled",
        disabled_reason="low quality",
    )


def _influencer_event(influencer):
    event = InfluencerEvent(
        id=uuid4_str(),
        created=dt.datetime.now(dt.timezone.utc),
        type="test_event",
        influencer_id=influencer.id,
    )
    influencer.events.append(event)
    return event


def _advertiser(region):
    return _advertiser_factory(primary_region=region)


def _user_advertiser_association(advertiser):
    return _user_advertiser_association_factory(advertiser=advertiser)


def _advertiser_config(advertiser):
    return _advertiser_config_factory(advertiser_id=advertiser.id)


def _advertiser_industry():
    return _advertiser_industry_factory()


def _email_login(user):
    obj = EmailLogin(
        email="valtyr@example.com", user_id=user.id, created=dt.datetime.now(dt.timezone.utc)
    )
    user.email_login = obj
    return obj


def _interest():
    return Interest(name="Fashion", id="a3cc0363-521c-4efd-9258-7d07389b6f1b")


def _post(campaign):
    return _post_factory(campaign=campaign)


def _targeting(region, campaign, interest):
    obj = Targeting(interest_ids=[interest["id"]], regions=[region], campaign=campaign)
    return obj


def _deleted_gig(post, offer):
    obj = _gig(post, offer)
    log = GigLog(obj)
    log.add_event("delete", {"reason": "Gig was cancelled"})
    return obj


def _gig(post, offer, state=GIG_STATES.APPROVED, submission=None, instagram_post=None):
    return _gig_factory(
        post=post, offer=offer, state=state, submission=submission, instagram_post=instagram_post
    )


def _insight(gig):
    return Insight(id=uuid4_str(), state=Insight.STATES.SUBMITTED, gig=gig)


def _gig_with_gallery_media(post, offer):
    instagram_post_id = uuid4_str()
    instagram_post = InstagramPost(
        id=instagram_post_id,
        created=dt.datetime.now(dt.timezone.utc),
        comments=0,
        likes=0,
        media=[
            Image(
                url="https://host.com/fakepath/e35/image_name0.jpg",
                owner_id=instagram_post_id,
                owner_type="instagram_post",
            ),
            Image(
                url="https://host.com/fakepath/e35/image_name1.jpg",
                owner_id=instagram_post_id,
                owner_type="instagram_post",
            ),
            Video(
                url="https://host.com/fakepath/e35/image_name2.jpg",
                owner_id=instagram_post_id,
                owner_type="instagram_post",
                thumbnail="https://host.com/fakepath/e35/image_name2.jpg",
            ),
        ],
    )
    return _gig_factory(
        post=post, offer=offer, instagram_post=instagram_post, state=GIG_STATES.APPROVED
    )


def _story_frame(influencer):
    return _story_frame_factory(influencer=influencer)


def _instagram_story(gig):
    return _instagram_story_factory(gig=gig)


def _instagram_post(gig):
    return _instagram_post_factory(gig=gig)


def _instagram_post_comment(instagram_post):
    return InstagramPostComment(
        ig_comment_id=uuid4_str(),
        username="username",
        text="comment",
        instagram_post=instagram_post,
    )


def _instagram_post_insight(instagram_post):
    return InstagramPostInsight(
        engagement=100,
        impressions=200,
        instagram_post_id=instagram_post.id,
    )


def _instagram_story_frame_insight(story_frame):
    return InstagramStoryFrameInsight(story_frame_id=story_frame.id, replies=101)


def _instagram_post_gallery(gig):
    instagram_post_id = uuid4_str()
    return _instagram_post_factory(
        id=instagram_post_id,
        gig=gig,
        media=[
            Image(
                url="https://host.com/fakepath/e35/image_name0.jpg",
                owner_id=instagram_post_id,
                owner_type="instagram_post",
            ),
            Image(
                url="https://host.com/fakepath/e35/image_name1.jpg",
                owner_id=instagram_post_id,
                owner_type="instagram_post",
            ),
            Video(
                url="https://host.com/fakepath/e35/video_name2.mp4",
                owner_id=instagram_post_id,
                owner_type="instagram_post",
                thumbnail="https://host.com/fakepath/e35/thumbnail2.jpg",
            ),
        ],
    )


def _submission(gig):
    return _submission_factory(gig=gig)


def _submission_gallery(gig):
    submission_id = uuid4_str()
    return _submission_factory(
        id=submission_id,
        gig=gig,
        media=[
            Image(
                url="https://host.com/fakepath/e35/image_name0.jpg",
                owner_id=submission_id,
                owner_type="submission",
            ),
            Image(
                url="https://host.com/fakepath/e35/image_name1.jpg",
                owner_id=submission_id,
                owner_type="submission",
            ),
            Video(
                url="https://host.com/fakepath/e35/video_name2.mp4",
                owner_id=submission_id,
                owner_type="submission",
                thumbnail="https://host.com/fakepath/e35/thumbnail2.jpg",
            ),
        ],
    )


def _region(market, locale_code="en_GB"):
    return _region_factory(market_slug=market.slug, locale_code=locale_code)


def _campaign(advertiser, region, **kwargs):
    kwargs.update({"advertiser": advertiser, "region": region})
    return _campaign_factory(**kwargs)


def _campaign_metric(campaign):
    return _campaign_metric_factory(campaign=campaign)


def _region_state(region):
    return _region_factory(
        name="England",
        locale_code=region.locale_code,
        market_slug=region.market_slug,
        path=[region.id],
    )


def _region_city(region, region_state):
    return _region_factory(
        name="London",
        locale_code=region.locale_code,
        market_slug=region.market_slug,
        path=[region.id, region_state.id],
    )


def _device(influencer_user):
    return Device(
        id="4970ea63-fc0c-4b14-9594-a805f17d5468",
        device_token="eca7108b4e3e43e9cc9ebda8d0b30038c2bc2aa3e77e58986beb8921d9cf3f89",
        device_model="iStone 7.0",
        os_version="iOS 1337.0",
        last_used=dt.datetime.now(dt.timezone.utc),
    )


def _instagram_account():
    return _instagram_account_factory()


def _audit(influencer):
    return _audit_factory(influencer=influencer)


def _offer(campaign, influencer):
    return _offer_factory(campaign=campaign, influencer=influencer)


def _payment(offer):
    return _payment_factory(offer=offer)


def _address(influencer):
    return Address(
        id=uuid4_str(),
        created=dt.datetime.now(dt.timezone.utc),
        modified=dt.datetime.now(dt.timezone.utc),
        influencer=influencer,
        influencer_id=influencer.id,
        address1="20th Century Theatre",
        address2="291 Westbourne Grove",
        postal_code="MOCK3D",
        city="London",
        country="GB",
        is_pobox=False,
        is_commercial=True,
    )


def _user(role_name):
    return _user_factory(role_name=role_name, birthday=dt.date(1993, 1, 1))


def _advertiser_user(advertiser, access_level):
    user = _user_factory(role_name="advertiser")
    create_user_advertiser_association(user, advertiser, access_level)
    return user


def _facebook_account(user=None):
    return FacebookAccount(facebook_name="", facebook_user_id="", token="", users=[user])


def _tax_form(influencer):
    return TaxForm(influencer=influencer, number="w9")
