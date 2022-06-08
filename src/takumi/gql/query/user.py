from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.orm import lazyload
from sqlalchemy.sql.expression import desc

from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.gql.db import filter_advertisers, filter_users
from takumi.models import Advertiser, Campaign, EmailLogin, User, UserAdvertiserAssociation
from takumi.roles import permissions
from takumi.roles.roles import InfluencerRole
from takumi.search import search_advertiser_users_query


class UserQuery:
    user = fields.Field("User", id=arguments.UUID(required=True))
    current_user = fields.Field("User")
    users = fields.ConnectionField(
        "UserConnection",
        role_name=arguments.List(arguments.String),
        active=arguments.Boolean(
            required=False, description="Filter active(default) or inactive users"
        ),
        search=arguments.String(
            required=False, description="Search through advertiser users by name or email"
        ),
        include_influencers=arguments.Boolean(),
    )
    users_for_advertiser = fields.ConnectionField(
        "UserConnection", domain=arguments.String(required=True)
    )
    pending_users = fields.ConnectionField("UserConnection")
    users_by_assigned_campaign_count = fields.List("UserCount")
    brand_profile_user_for_advertiser = fields.Field("User", id=arguments.UUID(required=True))

    @permissions.public.require()
    def resolve_user(root, info, id):
        query = filter_users()
        return query.filter(User.id == id).one_or_none()

    @permissions.public.require()
    def resolve_current_user(root, info):
        return current_user

    @permissions.public.require()
    def resolve_users(
        root, info, role_name=None, active=True, search=None, include_influencers=True
    ):
        query = filter_users().filter(EmailLogin.verified == True, User.active == active)

        if role_name is not None:
            query = query.filter(User.role_name.in_(role_name))

        if include_influencers is False:
            query = query.filter(User.role_name != "influencer")

        if search is not None:
            query = search_advertiser_users_query(
                query, search, sort=True
            )  # XXX: created order overrides sort?

        return query.order_by(User.created.desc())

    @permissions.team_member.require()
    def resolve_pending_users(root, info):
        query = filter_users().filter(
            EmailLogin.verified == False, User.role_name != InfluencerRole.name
        )
        return query.order_by(User.created.desc())

    @permissions.public.require()
    def resolve_users_for_advertiser(root, info, domain):
        query = filter_advertisers()
        advertiser = query.filter(Advertiser.domain == domain).one_or_none()

        if advertiser is None:
            return None

        return (
            User.query.join(UserAdvertiserAssociation, User.id == UserAdvertiserAssociation.user_id)
            .filter(
                UserAdvertiserAssociation.advertiser_id == advertiser.id,
                User.active == True,
                UserAdvertiserAssociation.access_level != "brand_profile",
            )
            .order_by(User.created.desc())
        )

    @permissions.public.require()
    def resolve_brand_profile_user_for_advertiser(root, info, id):
        query = filter_advertisers()
        advertiser = query.filter(Advertiser.id == id).one_or_none()

        if advertiser is None:
            return None
        brand_profile_user = (
            User.query.join(UserAdvertiserAssociation, User.id == UserAdvertiserAssociation.user_id)
            .filter(
                UserAdvertiserAssociation.advertiser_id == advertiser.id,
                UserAdvertiserAssociation.access_level == "brand_profile",
            )
            .one_or_none()
        )
        return brand_profile_user

    @permissions.team_member.require()
    def resolve_users_by_assigned_campaign_count(root, info):
        query = (
            db.session.query(User, func.count(Campaign.id).label("campaign_count"))
            .join(
                Campaign,
                or_(
                    Campaign.campaign_manager_id == User.id,
                    Campaign.community_manager_id == User.id,
                ),
            )
            .filter(Campaign.state == "launched")
            .group_by(User.id)
            .order_by(desc("campaign_count"))
            # EmailLogin is eagerly joined in the model, but we don't want to group by it here.
            .options(lazyload(User.email_login))
        )

        return [dict(user=user, count=count) for (user, count) in query]
