import datetime as dt

from flask_login import current_user
from sqlalchemy import desc, func, or_

from takumi.constants import (
    SUPPORTED_GIG_EVENTS,
    SUPPORTED_INFLUENCER_HISTORY_EVENTS,
    SUPPORTED_OFFER_EVENTS,
)
from takumi.gql import arguments, fields
from takumi.gql.db import filter_influencers
from takumi.gql.exceptions import GraphQLException
from takumi.ig.profile import refresh_on_interval
from takumi.models import Influencer, InstagramAccount, User
from takumi.roles import permissions
from takumi.serializers import InfluencerHistorySerializer
from takumi.services import InfluencerService

from .influencers import InfluencerGraphQLSearch, InfluencerStatsResults


class EventType(arguments.Enum):
    only_influencer_events = "only_influencer_events"
    only_offer_events = "only_offer_events"
    only_gig_events = "only_gig_events"


def _get_count_by(info):
    if hasattr(info, "field_asts") and info.field_asts:
        field = info.field_asts[0]
        count_by = (
            next((x for x in field.selection_set.selections if x.name.value == "countBy"), None)
            if field
            else None
        )
        if count_by:
            field = next(a for a in count_by.arguments if a.name.value == "fields")
            values = field.value.values if hasattr(field.value, "values") else [field.value]
            return [v.value for v in values]
    return None


def format_date(date):
    try:
        return dt.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        raise ValueError(f'"{date}" is not on the correct date format')


class InfluencerQuery:
    influencer = fields.Field(
        "Influencer", username=arguments.String(), id=arguments.UUID(), refresh=arguments.Boolean()
    )
    current_influencer = fields.Field("Influencer")
    influencers = fields.InfluencerConnectionField(
        "InfluencerConnection", limit=arguments.Int(), **InfluencerGraphQLSearch.ARGUMENTS_WITH_SORT
    )
    targeted_influencers_for_campaign = fields.ConnectionField(
        "InfluencerConnection", id=arguments.UUID(required=True)
    )
    influencer_events = fields.ConnectionField(
        "InfluencerEventsConnection",
        username=arguments.String(),
        id=arguments.UUID(),
        event_type=EventType(),
        date_from=arguments.String(),
        date_to=arguments.String(),
    )
    influencer_stats = fields.Field(InfluencerStatsResults, **InfluencerGraphQLSearch.ARGUMENTS)

    @permissions.public.require()
    def resolve_influencer(root, info, username=None, id=None, refresh=True):
        query = filter_influencers()
        if not any([username, id]):
            raise GraphQLException(
                "Can not resolve an influencer without either `id` or `username`"
            )

        if username is not None:
            query = query.filter(
                or_(
                    func.lower(InstagramAccount.ig_username) == username.strip().lower(),
                    func.lower(User.tiktok_username) == username.strip().lower(),
                ),
            )
        elif id is not None:
            query = query.filter(Influencer.id == id)
        influencer = query.one_or_none()

        if influencer is None:
            if username is not None:
                influencer = Influencer.from_url(username.strip())
                if influencer is None:
                    return None
            else:
                return None

        # refresh the influencer, a side-effect, but we want the fetched
        # influencer to be up to date
        if refresh:
            refresh_on_interval(influencer)

        return influencer

    @permissions.team_member.require()
    def resolve_influencer_stats(root, info, **params):
        search = InfluencerGraphQLSearch(params)
        search.add_statistics_aggregations()
        results = search.execute()
        return InfluencerGraphQLSearch.extract_aggs(results)

    @permissions.public.require()
    def resolve_current_influencer(root, info):
        return current_user.influencer

    @permissions.access_all_influencers.require()  # noqa
    def resolve_influencers(root, info, **params):
        limit = params.pop("limit", None)
        params["count_by"] = _get_count_by(info)
        results = InfluencerGraphQLSearch(params).execute()
        if limit:
            results = results[0:limit]
        return results

    @permissions.public.require()
    def resolve_influencer_events(
        root, info, username=None, id=None, event_type=None, date_from=None, date_to=None
    ):
        if not any([username, id]):
            raise GraphQLException(
                "Can not resolve an influencer without either `id` or `username`"
            )
        if username:
            influencer = (
                filter_influencers().filter(InstagramAccount.ig_username == username).one_or_none()
            )
        if id:
            influencer = filter_influencers().filter(Influencer.id == id).one_or_none()

        if influencer is None:
            raise GraphQLException("Influencer ({}) not found".format(username or id))

        from_date = None if date_from is None else format_date(date_from)
        to_date = None if date_to is None else format_date(date_to)

        if event_type == EventType.only_influencer_events:
            events = InfluencerService.get_influencer_events(
                influencer.id, SUPPORTED_INFLUENCER_HISTORY_EVENTS, from_date, to_date
            )
        elif event_type == EventType.only_gig_events:
            events = InfluencerService.get_gig_events(
                influencer.id, SUPPORTED_GIG_EVENTS, from_date, to_date
            )
        elif event_type == EventType.only_offer_events:
            events = InfluencerService.get_offer_events(
                influencer.id, SUPPORTED_OFFER_EVENTS, from_date, to_date
            )
        else:
            influencer_events = InfluencerService.get_influencer_events(
                influencer.id, SUPPORTED_INFLUENCER_HISTORY_EVENTS, from_date, to_date
            )
            gig_events = InfluencerService.get_gig_events(
                influencer.id, SUPPORTED_GIG_EVENTS, from_date, to_date
            )
            offer_events = InfluencerService.get_offer_events(
                influencer.id, SUPPORTED_OFFER_EVENTS, from_date, to_date
            )

            events = influencer_events.union_all(gig_events, offer_events)

        serializer = InfluencerHistorySerializer(events.order_by(desc("created")))
        return serializer.serialize()
