import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy_utils import create_database, drop_database

import takumi.alembic.utils as alembic_utils
from takumi.extensions import db as _db
from takumi.extensions import elasticsearch as _elasticsearch
from takumi.models import PostInsight, StoryInsight
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.market import us_market
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.post import PostTypes
from takumi.search.influencer import InfluencerIndex, update_influencer_info

from ..utils import (
    _address,
    _advertiser,
    _advertiser_config,
    _advertiser_industry,
    _advertiser_user,
    _audit,
    _campaign,
    _campaign_metric,
    _device,
    _facebook_account,
    _gig,
    _insight,
    _instagram_account,
    _instagram_post,
    _instagram_post_comment,
    _instagram_post_insight,
    _instagram_story,
    _instagram_story_frame_insight,
    _interest,
    _offer,
    _payment,
    _post,
    _region,
    _region_city,
    _region_state,
    _reviewed_influencer,
    _story_frame,
    _submission,
    _tax_form,
    _user_advertiser_association,
    _verified_influencer,
)


@pytest.fixture(scope="function")
def elasticsearch(app):
    client = _elasticsearch._get_raw_client()
    index = app.config["ELASTICSEARCH_INFLUENCER_INDEX"]
    try:
        _elasticsearch.indices.create(index=index)
    except Exception as e:
        if hasattr(e, "error") and e.error == "resource_already_exists_exception":
            pass
        else:
            raise e
    for doc_type, mapping in InfluencerIndex._mappings:
        _elasticsearch.indices.put_mapping(index=index, doc_type=doc_type, body=mapping)
    yield _elasticsearch
    client.indices.delete(index=index)


@pytest.fixture(scope="function")
def update_influencer_es(elasticsearch):
    def inner(influencer_id):
        update_influencer_info(influencer_id)
        elasticsearch.indices.refresh()

    return inner


@pytest.fixture(scope="session")
def db(app):
    alembic_utils.create_all(_db)

    yield _db

    database_uri = str(_db.engine.url)
    drop_database(database_uri)
    create_database(database_uri)

    engine = create_engine(database_uri)
    engine.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    engine.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")


@pytest.fixture(scope="function")
def db_session(db):
    """PostgreSQL supports nested or checkpointed commits which we can use
    to a speed advantage in integration tests. Basically nothing ever gets
    written when using this fixture.
    """
    connection = db.engine.connect()
    trans = connection.begin()
    db.session.configure(bind=connection, binds={})

    yield db.session

    trans.rollback()
    connection.close()
    db.session.remove()


@pytest.fixture(scope="function")
def db_advertiser_user(db_session, db_advertiser):
    advertiser_user = _advertiser_user(db_advertiser, "member")
    db_session.add(advertiser_user)
    db_session.commit()
    yield advertiser_user


@pytest.fixture(scope="function")
def db_advertiser_brand_profile_user(db_session, db_advertiser):
    advertiser_user = _advertiser_user(db_advertiser, "brand_profile")
    db_session.add(advertiser_user)
    db_session.commit()
    yield advertiser_user


@pytest.fixture(scope="function")
def db_advertiser_owner_user(db_session, db_advertiser):
    advertiser_user = _advertiser_user(db_advertiser, "owner")
    db_session.add(advertiser_user)
    db_session.commit()
    yield advertiser_user


@pytest.fixture(scope="function")
def db_advertiser_industry():
    yield _advertiser_industry()


@pytest.fixture(scope="function")
def db_developer_user(db_session, developer_user):
    db_session.add(developer_user)
    db_session.commit()
    yield developer_user


@pytest.fixture(scope="function")
def db_influencer_user(db_session, influencer_user):
    db_session.add(influencer_user)
    db_session.commit()
    yield influencer_user


@pytest.fixture(scope="function")
def db_advertiser(db_session, db_region):
    obj = _advertiser(db_region)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_brand_profile_user(db_session, db_advertiser):
    advertiser_config = _advertiser_config(db_advertiser)
    user_advertiser_association = _user_advertiser_association(db_advertiser)
    db_advertiser.advertiser_config = advertiser_config
    db_session.add(db_advertiser)
    db_session.add(user_advertiser_association)
    db_session.commit()
    yield db_advertiser.users[0]


@pytest.fixture(scope="function")
def db_facebook_account(db_session, db_influencer_user):
    obj = _facebook_account(db_influencer_user)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_offer(db_session, db_campaign, db_influencer):
    obj = _offer(db_campaign, db_influencer)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_payable_offer(db_session, db_offer, db_post, db_gig):
    db_offer.reward = 100 * 100
    db_offer.state = OFFER_STATES.ACCEPTED
    db_offer.is_claimable = True
    db_offer.payable = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    db_offer.accepted = dt.datetime.now(dt.timezone.utc)
    db_session.add(db_offer)
    db_session.commit()
    yield db_offer


@pytest.fixture(scope="function")
def db_reviewed_influencer(db_influencer_user, db_instagram_account, db_region, db_session):
    obj = _reviewed_influencer(
        db_influencer_user, db_region, instagram_account=db_instagram_account
    )
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def db_interest(db_session):
    obj = _interest()
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def db_influencer(
    db_influencer_user,
    db_instagram_account,
    db_facebook_account,
    db_region,
    db_session,
    db_interest,
):
    obj = _verified_influencer(
        db_influencer_user,
        db_region,
        instagram_account=db_instagram_account,
        interests=[db_interest],
    )
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def es_influencer(
    db_influencer_user,
    db_instagram_account,
    db_region,
    db_session,
    update_influencer_es,
    db_interest,
):
    obj = _verified_influencer(
        db_influencer_user,
        db_region,
        instagram_account=db_instagram_account,
        interests=[db_interest],
    )
    db_session.add(obj)
    update_influencer_es(obj.id)
    yield obj


@pytest.fixture(scope="function")
def db_instagram_account(db_session):
    obj = _instagram_account()
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def db_region(db_session, market):
    obj = _region(market=market)
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def db_audit(db_session, db_influencer):
    obj = _audit(db_influencer)
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def db_campaign(db_session, db_advertiser, db_region):
    obj = _campaign(advertiser=db_advertiser, region=db_region)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_campaign_metric(db_session, db_campaign):
    obj = _campaign_metric(db_campaign)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_reach_campaign(db_session, db_advertiser, db_region):
    obj = _campaign(advertiser=db_advertiser, region=db_region, reward_model="reach")
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def db_impressions_campaign(db_session, db_advertiser, db_region):
    obj = _campaign(advertiser=db_advertiser, region=db_region, reward_model="impressions")
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def db_cash_campaign(db_session, db_advertiser, db_region):
    obj = _campaign(advertiser=db_advertiser, region=db_region, reward_model="cash")
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def db_us_region(db_session):
    obj = _region(market=us_market, locale_code="en_US")
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def db_region_state(db_session, db_region):
    obj = _region_state(db_region)
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def db_region_city(db_session, db_region, db_region_state):
    obj = _region_city(db_region, db_region_state)
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def db_assets_post(db_session, db_campaign):
    obj = _post(db_campaign)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_post(db_session, db_campaign):
    obj = _post(db_campaign)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_post_story(db_session, db_campaign):
    obj = _post(db_campaign)
    obj.post_type = "story"
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_reach_post(db_session, db_reach_campaign):
    obj = _post(db_reach_campaign)

    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_impressions_post(db_session, db_impressions_campaign):
    obj = _post(db_impressions_campaign)

    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_cash_post(db_session, db_cash_campaign):
    obj = _post(db_cash_campaign)

    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_us_campaign(db_session, db_advertiser, db_us_region):
    obj = _campaign(db_advertiser, region=db_us_region)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_us_reach_campaign(db_session, db_advertiser, db_us_region):
    obj = _campaign(db_advertiser, region=db_us_region, reward_model="reach")
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_2xassets_post(db_session, db_assets_post):
    db_assets_post.reward_multiplier = 2
    db_session.add(db_assets_post)
    db_session.commit()
    yield db_assets_post


@pytest.fixture(scope="function")
def db_gig(db_post, db_offer, db_session):
    db_offer.state = OFFER_STATES.ACCEPTED
    obj = _gig(db_post, db_offer)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_gig_story(db_post_story, db_offer, db_session):
    db_offer.state = OFFER_STATES.ACCEPTED
    obj = _gig(db_post_story, db_offer)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_insight(db_gig):
    obj = _insight(db_gig)
    yield obj


@pytest.fixture(scope="function")
def db_submission(db_gig_story, db_session):
    obj = _submission(gig=db_gig_story)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_posted_gig(db_post, db_offer, db_session):
    db_offer.state = OFFER_STATES.ACCEPTED
    obj = _gig(db_post, db_offer)
    obj.is_verified = True
    submission = _submission(gig=obj)
    instagram_post = _instagram_post(gig=obj)
    db_session.add(obj)
    db_session.add(submission)
    db_session.add(instagram_post)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_story_frame(db_influencer, db_session):
    obj = _story_frame(influencer=db_influencer)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_instagram_story(db_gig_story, db_session):
    db_gig_story.post.post_type = PostTypes.story
    obj = _instagram_story(gig=db_gig_story)
    db_gig_story.state = GIG_STATES.APPROVED
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_instagram_post(db_gig, db_session):
    obj = _instagram_post(gig=db_gig)
    db_gig.state = GIG_STATES.APPROVED
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_story_insight(db_instagram_story, db_session):
    obj = StoryInsight(gig=db_instagram_story.gig)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_post_insight(db_instagram_post, db_session):
    obj = PostInsight(gig=db_instagram_post.gig)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_instagram_post_comment(db_instagram_post, db_session):
    obj = _instagram_post_comment(instagram_post=db_instagram_post)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_instagram_post_insight(db_instagram_post, db_session):
    obj = _instagram_post_insight(instagram_post=db_instagram_post)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_instagram_story_frame_insight(db_story_frame, db_session):
    obj = _instagram_story_frame_insight(story_frame=db_story_frame)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_reach_gig(db_reach_post, db_offer, db_session):
    db_offer.state = OFFER_STATES.ACCEPTED
    obj = _gig(db_reach_post, db_offer)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_device(db_influencer_user, db_session):
    obj = _device(db_influencer_user)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_address(db_influencer, db_session):
    obj = _address(db_influencer)
    db_session.add(obj)
    db_session.commit()
    yield obj


@pytest.fixture(scope="function")
def db_payment(db_offer, db_session):
    obj = _payment(db_offer)
    db_session.add(obj)
    yield obj


@pytest.fixture(scope="function")
def db_tax_form(db_influencer, db_session):
    obj = _tax_form(db_influencer)
    db_session.add(obj)
    db_session.commit()
    yield obj
