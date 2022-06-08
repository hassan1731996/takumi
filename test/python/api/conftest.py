# encoding=utf-8
import datetime as dt
from urllib.parse import SplitResult

import mock
import pytest
from httmock import HTTMock, all_requests
from requests.models import PreparedRequest

from core.testing.flask_client import TestClient
from core.testing.utils import (
    instalamb_mock,
    instascrape_mock,
    pwnedpasswords_mock,
    salesforce_mock,
    tasktiger_task,
)

from takumi.app import create_app
from takumi.models import Currency, Insight, Market
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.post import PostTypes
from takumi.utils import uuid4_str

from .utils import (
    _address,
    _advertiser,
    _advertiser_factory,
    _advertiser_industry,
    _advertiser_user,
    _audit_factory,
    _campaign,
    _campaign_factory,
    _deleted_gig,
    _device,
    _device_factory,
    _disabled_influencer,
    _email_login,
    _email_login_factory,
    _facebook_account,
    _facebook_account_factory,
    _gig,
    _gig_factory,
    _gig_with_gallery_media,
    _influencer,
    _influencer_event,
    _influencer_factory,
    _influencer_prospect,
    _instagram_account,
    _instagram_account_factory,
    _instagram_post,
    _instagram_post_factory,
    _instagram_post_gallery,
    _instagram_story,
    _instagram_story_factory,
    _interest,
    _offer,
    _offer_event_factory,
    _offer_factory,
    _payment,
    _payment_factory,
    _post,
    _post_factory,
    _region,
    _region_city,
    _region_factory,
    _region_state,
    _reviewed_influencer,
    _story_frame_factory,
    _submission,
    _submission_gallery,
    _tax_form,
    _user,
    _user_factory,
    _verified_influencer,
    passthrough_decorator,
)

# Mock tasktiger.task asap, since it exposes a decorator that's used for tasks
# and we need to mock tiger before any of those definitions are loaded in
mock.patch("takumi.extensions.tiger.task", side_effect=tasktiger_task).start()  # noqa


# Disable the .limit method of Flask-Limiter while testing
mocked_limiter = mock.patch("takumi.extensions.limiter.limit", passthrough_decorator).start()
# Disable the advertiser_auth decorator
mocked_advertiser_auth = mock.patch("takumi.auth.advertiser_auth", passthrough_decorator).start()


def _app():
    from takumi.constants import MINIMUM_CLIENT_VERSION

    with mock.patch("takumi.app.StatsD"):  # prevent udp traffic to localhost while testing
        app = create_app(testing=True)
        TestClient.VERSION = ".".join(map(str, MINIMUM_CLIENT_VERSION))
        app.test_client_class = TestClient
        with app.app_context():
            yield app


@pytest.fixture(scope="session")
def app():
    yield from _app()


@pytest.fixture(scope="function")
def disable_influencer_total_rewards(request, monkeypatch):
    monkeypatch.setattr(
        "takumi.models.influencer.Influencer.total_rewards", Currency(amount=0, currency="GBP")
    )


@pytest.fixture(autouse=True)
def slack_post():
    with mock.patch("takumi.slack.client.SlackClient.post_message") as mock_post:
        yield mock_post


@pytest.fixture(autouse=True)
def mock_ses():
    with mock.patch("takumi._boto.connections._ses") as mock_ses:
        yield mock_ses


@pytest.fixture(autouse=True)
def no_redis_lock(monkeypatch):
    with mock.patch("redis.lock.Lock.acquire"), mock.patch("redis.lock.Lock.release"):
        yield


@pytest.fixture()
def mock_redis_connection():
    with mock.patch("takumi.extensions.redis.get_connection") as mock_redis_connection:
        yield mock_redis_connection.return_value


@pytest.fixture(autouse=True)
def mock_s3():
    with mock.patch("takumi._boto.connections._s3") as mock_s3:
        yield mock_s3


@pytest.fixture(autouse=True)
def mock_mediaconvert():
    with mock.patch("takumi._boto.connections._mediaconvert") as mock_mediaconvert:
        yield mock_mediaconvert


@pytest.fixture(autouse=True)
def mock_textract():
    with mock.patch("takumi._boto.connections._textract") as mock_textract:
        yield mock_textract


@pytest.fixture(scope="function")
def mock_statsd(app):
    statsd = mock.Mock()
    app.config["statsd"] = statsd
    yield statsd


@pytest.fixture(scope="function")
def uk_ip_address():
    with mock.patch("core.geo.geo.geo_request.country_code") as mock_geo_request:
        mock_geo_request.return_value = "GB"
        yield


@pytest.fixture(autouse=True)
def mock_instascrape_profile():
    with HTTMock(instascrape_mock(r".*/users/[a-zA-Z0-9_\.]{3,}/?$", "profile.json")):
        yield


@pytest.fixture(autouse=True)
def mock_instascrape_recent_posts():
    with HTTMock(instascrape_mock(r".*/users/[a-zA-Z0-9_\.]{3,}/media/?$", "recent_media.json")):
        yield


@pytest.fixture(autouse=True)
def mock_instascrape_post():
    with HTTMock(instascrape_mock(".*/media/.*$", "media.json")):
        yield


@pytest.fixture(autouse=True)
def mock_insta_lamb_get():
    def mock_insta_lamb(self, query):
        if "media" in query:
            return instalamb_mock("media.json")
        if "user" in query:
            return instalamb_mock("profile.json")
        if "user_media" in query:
            return instalamb_mock("recent_media.json")

        raise Exception(query)

    with mock.patch("takumi.ig.instascrape.Instascrape._insta_lamb_get", mock_insta_lamb):
        yield


@pytest.fixture(autouse=True)
def mock_salesforce_requests():
    with HTTMock(salesforce_mock()):
        yield


@pytest.fixture(autouse=True)
def mock_pwnedpasswords_requests():
    with HTTMock(pwnedpasswords_mock()):
        yield


@pytest.fixture(autouse=True)
def mock_all_requests():
    """A catch-all request mock, to prevent tests from accidentally making requests

    Important: This mock must be below all other HTTMocks, since it's a catch-all
    """

    class TestDoingRequestException(Exception):
        pass

    @all_requests
    def response_content(url: SplitResult, request: PreparedRequest) -> None:
        raise TestDoingRequestException(f"[{request.method}]: {url.geturl()}")

    with HTTMock(response_content):
        yield


# ---- Object factories ---


@pytest.fixture(scope="function")
def device_factory():
    yield _device_factory


@pytest.fixture(scope="function")
def region_factory():
    yield _region_factory


@pytest.fixture(scope="function")
def email_login_factory():
    yield _email_login_factory


@pytest.fixture(scope="function")
def user_factory():
    yield _user_factory


@pytest.fixture(scope="function")
def audit_factory():
    yield _audit_factory


@pytest.fixture(scope="function")
def facebook_account_factory():
    yield _facebook_account_factory


@pytest.fixture(scope="function")
def influencer_factory():
    yield _influencer_factory


@pytest.fixture(scope="function")
def instagram_account_factory():
    yield _instagram_account_factory


@pytest.fixture(scope="function")
def advertiser_factory():
    yield _advertiser_factory


@pytest.fixture(scope="function")
def campaign_factory():
    yield _campaign_factory


@pytest.fixture(scope="function")
def post_factory():
    yield _post_factory


@pytest.fixture(scope="function")
def offer_factory():
    yield _offer_factory


@pytest.fixture(scope="function")
def offer_event_factory():
    yield _offer_event_factory


@pytest.fixture(scope="function")
def gig_factory():
    yield _gig_factory


@pytest.fixture(scope="function")
def instagram_story_factory():
    yield _instagram_story_factory


@pytest.fixture(scope="function")
def story_frame_factory():
    yield _story_frame_factory


@pytest.fixture(scope="function")
def instagram_post_factory():
    yield _instagram_post_factory


@pytest.fixture(scope="function")
def payment_factory():
    yield _payment_factory


# ---- Fixtures ----
@pytest.fixture(scope="function")
def session():
    with mock.patch("takumi.extensions.db.session") as mock_session:
        yield mock_session


@pytest.fixture(scope="function")
def advertiser_user(app, advertiser):
    yield _advertiser_user(advertiser, "member")


@pytest.fixture(scope="function")
def advertiser_admin_user(app, advertiser):
    yield _advertiser_user(advertiser, "admin")


@pytest.fixture(scope="function")
def advertiser_owner_user(app, advertiser):
    yield _advertiser_user(advertiser, "owner")


@pytest.fixture(scope="function")
def advertiser_brand_profile_user(app, advertiser):
    yield _advertiser_user(advertiser, "brand_profile")


@pytest.fixture(scope="function")
def developer_user(app):
    yield _user("developer")


@pytest.fixture(scope="function")
def influencer_user(app):
    yield _user("influencer")


@pytest.fixture(scope="function")
def campaign_manager(app):
    yield _user("campaign_manager")


@pytest.fixture(scope="function")
def account_manager(app):
    yield _user("account_manager")


@pytest.fixture(scope="function")
def client(app):
    yield app.test_client()


@pytest.fixture(scope="function")
def advertiser_client(advertiser_user, client):
    with client.use(advertiser_user):
        yield client


@pytest.fixture(scope="function")
def advertiser_admin_client(advertiser_admin_user, client):
    with client.use(advertiser_admin_user):
        yield client


@pytest.fixture(scope="function")
def advertiser_owner_client(advertiser_owner_user, client):
    with client.use(advertiser_owner_user):
        yield client


@pytest.fixture(scope="function")
def db_advertiser_owner_client(db_advertiser_owner_user, client):
    with client.use(db_advertiser_owner_user):
        yield client


@pytest.fixture(scope="function")
def db_advertiser_client(db_advertiser_user, client):
    with client.use(db_advertiser_user):
        yield client


@pytest.fixture(scope="function")
def developer_client(developer_user, client):
    with client.use(developer_user):
        yield client


@pytest.fixture(scope="function")
def influencer_client(influencer_user, client):
    with client.use(influencer_user):
        yield client


@pytest.fixture(scope="function")
def influencer(influencer_user, region, instagram_account):
    yield _influencer(influencer_user, region, instagram_account)


@pytest.fixture(scope="function")
def reviewed_influencer(influencer_user, region, instagram_account):
    yield _reviewed_influencer(influencer_user, region, instagram_account)


@pytest.fixture(scope="function")
def verified_influencer(influencer_user, region, instagram_account):
    yield _verified_influencer(influencer_user, region, instagram_account)


@pytest.fixture(scope="function")
def disabled_influencer(influencer_user, region, instagram_account):
    yield _disabled_influencer(influencer_user, region, instagram_account)


@pytest.fixture(scope="function")
def influencer_event(influencer):
    yield _influencer_event(influencer)


@pytest.fixture(scope="function")
def advertiser(region):
    yield _advertiser(region)


@pytest.fixture(scope="function")
def advertiser_industry():
    yield _advertiser_industry()


@pytest.fixture(scope="function")
def region(market):
    yield _region(market)


@pytest.fixture(scope="function")
def interest():
    yield _interest()


@pytest.fixture(scope="function")
def campaign(advertiser, region):
    yield _campaign(advertiser, region)


@pytest.fixture(scope="function")
def offer(campaign, influencer):
    yield _offer(campaign, influencer)


@pytest.fixture(scope="function")
def region_state(region):
    yield _region_state(region)


@pytest.fixture(scope="function")
def region_city(region, region_state):
    yield _region_city(region, region_state)


@pytest.fixture(scope="function")
def market():
    yield Market.get_market("uk")


@pytest.fixture(scope="function")
def influencer_prospect():
    yield _influencer_prospect()


@pytest.fixture(scope="function")
def email_login(advertiser_user):
    yield _email_login(advertiser_user)


@pytest.fixture(scope="function")
def mock_ads_api():
    magic = mock.MagicMock()
    with mock.patch(
        "takumi.models.facebook_account.FacebookAccount.ads_api",
        new_callable=mock.PropertyMock,
        return_value=magic,
    ):
        yield magic


@pytest.fixture(scope="function")
def facebook_account():
    yield _facebook_account()


@pytest.fixture(scope="function")
def email_otp_login(influencer_user):
    login = _email_login(influencer_user)
    login.reset_otp()
    yield login


@pytest.fixture(scope="function")
def post(campaign):
    yield _post(campaign)


@pytest.fixture(scope="function")
def reach_campaign(advertiser, region):
    yield _campaign(advertiser, region, reward_model="reach", units=1_000_000)


@pytest.fixture(scope="function")
def engagement_campaign(advertiser, region):
    yield _campaign(advertiser, region, reward_model="engagement", units=100_000)


@pytest.fixture(scope="function")
def cash_campaign(advertiser, region):
    yield _campaign(advertiser, region, reward_model="cash", units=1000)


@pytest.fixture(scope="function")
def impressions_campaign(advertiser, region):
    yield _campaign(advertiser, region, reward_model="impressions", units=250_000)


@pytest.fixture(scope="function")
def reach_post(reach_campaign):
    yield _post(reach_campaign)


@pytest.fixture(scope="function")
def engagement_post(engagement_campaign):
    yield _post(engagement_campaign)


@pytest.fixture(scope="function")
def deleted_gig(post, offer):
    yield _deleted_gig(post, offer)


@pytest.fixture(scope="function")
def gig(post, offer):
    gig = _gig(post, offer, state=GIG_STATES.SUBMITTED)
    yield gig


@pytest.fixture(scope="function")
def posted_gig(post, offer):
    gig = _gig(post, offer, state=GIG_STATES.APPROVED)
    gig.submissions = [_submission(gig=gig)]
    gig.instagram_post = _instagram_post(gig=gig)
    gig.is_verified = True
    yield gig


@pytest.fixture(scope="function")
def instagram_post(posted_gig):
    yield posted_gig.instagram_post


@pytest.fixture(scope="function")
def instagram_post_gallery(gig):
    yield _instagram_post_gallery(gig=gig)


@pytest.fixture(scope="function")
def instagram_story(gig):
    gig.post.post_type = PostTypes.story
    yield _instagram_story(gig)


@pytest.fixture(scope="function")
def submission(gig):
    gig.submissions = [_submission(gig=gig)]
    yield gig.submission


@pytest.fixture(scope="function")
def post_insight(instagram_post):
    yield Insight(id=uuid4_str(), gig=instagram_post.gig)


@pytest.fixture(scope="function")
def story_insight(instagram_story):
    yield Insight(id=uuid4_str(), gig=instagram_story.gig)


@pytest.fixture(scope="function")
def submission_gallery(gig):
    yield _submission_gallery(gig=gig)


@pytest.fixture(scope="function")
def gig_with_gallery_media(post, offer):
    yield _gig_with_gallery_media(post, offer)


@pytest.fixture(scope="function")
def payable_offer(post, offer):
    offer.state = OFFER_STATES.ACCEPTED
    offer.is_claimable = True
    offer.payable = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    yield offer


@pytest.fixture(scope="function")
def device(influencer_user):
    yield _device(influencer_user)


@pytest.fixture(scope="function")
def instagram_account():
    yield _instagram_account()


@pytest.fixture(scope="function")
def address(influencer):
    yield _address(influencer)


@pytest.fixture(scope="function")
def payment(offer):
    yield _payment(offer)


@pytest.fixture(autouse=True)  # noqa
def tiger_task():  # noqa
    tasktiger_task.clear_tasks()
    yield tasktiger_task  # noqa


@pytest.fixture(scope="function")
def tax_form(influencer):
    yield _tax_form(influencer)
