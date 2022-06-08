import sys

from flask import current_app
from graphene import Schema
from sentry_sdk import capture_exception
from sqlalchemy import event
from tasktiger import RetryException, exponential

from core.common.monitoring import TimingStats
from core.elasticsearch import DictObject
from core.tasktiger import MAIN_QUEUE_NAME

from takumi.extensions import elasticsearch, tiger
from takumi.gql.generator import QueryGenerator
from takumi.models import Audit, FacebookPage, Influencer, InstagramAccount, Offer, User
from takumi.roles import system_access

from .audit.indexing import AUDIT_MAPPING
from .information.indexing import INFORMATION_MAPPING

INDEXING_QUEUE = f"{MAIN_QUEUE_NAME}.indexing"


class InfluencerInfo(DictObject):
    """Currently this type only exists for GraphQL union-typing reasons, and
    is a just a DictObject, but in the future could be defined properly to
    make the InfluencerInfo objects returned from ElasticSearch more useful.
    """

    pass


class IndexingError(Exception):
    def __init__(self, *args, **kwargs):
        if "errors" in kwargs:
            self.errors = kwargs.pop("errors")


class InfluencerIndex:
    _doc = "influencer"
    _schema = None
    _mappings = [
        [
            "influencer",
            {
                "properties": {
                    "id": {"type": "keyword"},
                    "username": {"type": "keyword"},
                    "tiktok_username": {"type": "keyword"},
                    "has_tiktok_account": {"type": "boolean"},
                    "has_youtube_channel": {"type": "boolean"},
                    "email": {"type": "keyword", "boost": 2},
                    "participating_campaign_ids": {"type": "keyword"},
                    "invited_campaign_ids": {"type": "keyword"},
                    "gender": {"type": "keyword"},
                    "state": {"type": "keyword"},
                    "is_signed_up": {"type": "boolean"},
                    "has_facebook_page": {"type": "boolean"},
                    "birthday": {"type": "date", "format": "yyyy-MM-dd"},
                    "user_created": {"type": "date", "format": "date_time"},
                    "last_login": {"type": "date", "format": "date_time"},
                    "last_active": {"type": "date", "format": "date_time"},
                    "total_rewards.value": {"type": "long"},
                    "engagement.value": {"type": "float"},
                    "target_region": {
                        "type": "nested",
                        "properties": {
                            "id": {"type": "keyword"},
                            "country": {"type": "text"},
                            "market_slug": {"type": "text"},
                            "supported": {"type": "boolean"},
                            "targetable": {"type": "boolean"},
                            "path": {"type": "keyword"},
                        },
                    },
                    "interests": {
                        "type": "nested",
                        "properties": {"id": {"type": "keyword"}, "name": {"type": "keyword"}},
                    },
                    "followers_history_anomalies": {
                        "type": "nested",
                        "properties": {
                            "follower_increase": {"type": "long"},
                            "date": {"type": "date", "format": "yyyy-MM-dd"},
                            "ignore": {"type": "boolean"},
                            "anomaly_factor": {"type": "float"},
                        },
                    },
                    "device": {
                        "type": "nested",
                        "properties": {
                            "active": {"type": "boolean"},
                            "build_version": {"type": "keyword"},
                            "created": {"type": "date", "format": "date_time"},
                            "device_model": {"type": "keyword"},
                            "last_used": {"type": "date", "format": "date_time"},
                            "os_version": {"type": "keyword"},
                            "platform": {"type": "keyword"},
                            "id": {"type": "keyword"},
                        },
                    },
                    "audit": AUDIT_MAPPING,
                    "information": INFORMATION_MAPPING,
                    "instagram_audience_insight": {
                        "type": "nested",
                        "properties": {
                            "id": {"type": "keyword"},
                            "created": {"type": "date", "format": "date_time"},
                            "region_insights": {
                                "type": "nested",
                                "properties": {
                                    "id": {"type": "keyword"},
                                    "follower_count": {"type": "long"},
                                    "follower_percentage.value": {"type": "float"},
                                    "region": {
                                        "type": "nested",
                                        "properties": {
                                            "id": {"type": "keyword"},
                                            "country": {"type": "text"},
                                            "market_slug": {"type": "text"},
                                            "supported": {"type": "boolean"},
                                            "targetable": {"type": "boolean"},
                                            "path": {"type": "keyword"},
                                        },
                                    },
                                },
                            },
                            "gender_age_insights": {
                                "type": "nested",
                                "properties": {
                                    "id": {"type": "keyword"},
                                    "created": {"type": "date", "format": "date_time"},
                                    "follower_count": {"type": "long"},
                                    "follower_percentage.value": {"type": "float"},
                                    "age_from": {"type": "long"},
                                    "age_to": {"type": "long"},
                                },
                            },
                        },
                    },
                }
            },
        ]
    ]

    @classmethod
    def get_schema(cls):
        if cls._schema is None:
            from takumi.gql.query import Query

            cls._schema = Schema(query=Query, auto_camelcase=False)
        return cls._schema

    @staticmethod
    def source_query(influencer_id):
        return "query InfluencerIndexQuery { %s }" % (
            QueryGenerator.generate_query("influencer", id=influencer_id, refresh=False)
        )

    @classmethod
    def delete(cls, influencer_id):
        return elasticsearch.delete(id=influencer_id)

    @classmethod
    def get_source_document(cls, influencer_id):
        with system_access():
            result = cls.get_schema().execute(cls.source_query(influencer_id))
        if result.data is not None:
            return result.data
        else:
            raise IndexingError("No data returned from GraphQL query!", errors=result.errors)

    @classmethod
    def update_from_source(cls, influencer_id):
        doc = cls.get_source_document(influencer_id)
        if doc.get("influencer") is not None:
            elasticsearch.index(id=influencer_id, body=doc["influencer"])


@tiger.task(queue=INDEXING_QUEUE, debounce=5000)
def update_influencer_info(influencer_id, source=None):
    with TimingStats(
        current_app.config["statsd"], "takumi.search.influencer.update_influencer_info"
    ) as metric:
        try:
            metric.tags.append(f"source:{source}")
            InfluencerIndex.update_from_source(influencer_id)
        except Exception as e:
            sys.stderr.write("Failed to update {}, exception: {}".format(influencer_id, str(e)))
            raise RetryException(
                method=exponential(60, 2, 5), original_traceback=True, log_error=True
            )


@event.listens_for(FacebookPage, "after_insert")
@event.listens_for(FacebookPage, "after_update")
@event.listens_for(FacebookPage, "after_delete")
def trigger_influencer_info_update_for_facebook_page(mapper, connection, target):
    try:
        facebook_account = target.facebook_account
        if facebook_account.users:
            influencer = facebook_account.users[0].influencer
            if influencer:
                update_influencer_info.delay(influencer.id, source="facebook_page")
    except AttributeError:
        capture_exception()


@event.listens_for(Audit, "after_insert")
@event.listens_for(Audit, "after_update")
def trigger_influencer_info_update_for_audit(mapper, connection, target):
    try:
        influencer = target.influencer
        update_influencer_info.delay(influencer.id, source="audit")
    except AttributeError:
        capture_exception()


@event.listens_for(User, "after_insert")
@event.listens_for(User, "after_update")
def trigger_influencer_info_update_for_user(mapper, connection, target):
    try:
        influencer = target.influencer
        if influencer:
            update_influencer_info.delay(influencer.id, source="user")
    except AttributeError:
        capture_exception()


@event.listens_for(Offer, "after_update")
def trigger_influencer_info_update_for_offer(mapper, connection, target):
    try:
        influencer = target.influencer
        update_influencer_info.delay(influencer.id, source="offer")
    except AttributeError:
        capture_exception()


@event.listens_for(InstagramAccount, "after_update")
def trigger_influencer_info_update_for_instagram_account(mapper, connection, target):
    try:
        influencer = target.influencer
        if influencer is not None:
            update_influencer_info.delay(influencer.id, source="instagram_account")
    except AttributeError:
        capture_exception()


@event.listens_for(Influencer, "after_insert")
@event.listens_for(Influencer, "after_update")
def trigger_influencer_info_update(mapper, connection, target):
    influencer = target
    update_influencer_info.delay(influencer.id, source="influencer")
