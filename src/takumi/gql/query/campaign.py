import datetime as dt
import re
from collections import OrderedDict

from flask_login import current_user
from sqlalchemy import and_, or_

from takumi.campaign_stats import CampaignStats
from takumi.extensions import db
from takumi.gql import arguments, constants, fields
from takumi.gql.db import (
    filter_campaigns,
    filter_campaigns_by_advertiser_name,
    filter_campaigns_by_campaign_filters,
    filter_campaigns_by_date_range,
    filter_campaigns_by_industry,
    filter_campaigns_by_region,
    filter_campaigns_by_search_string,
    filter_mine_campaigns,
    filter_unassigned_campaigns,
    paginate_query,
    sort_campaigns_by_order,
)
from takumi.gql.utils import get_campaign_or_404, get_influencer_or_404
from takumi.models import Advertiser, Campaign, Influencer, Offer, Region
from takumi.models.targeting import get_influencer_targeting_filters
from takumi.roles import permissions


class CampaignQuery:
    campaign = fields.Field("Campaign", id=arguments.UUID(required=True))
    campaigns = fields.ConnectionField(
        "CampaignConnection",
        mine=arguments.Boolean(),
        region_id=arguments.UUID(),
        search=arguments.String(),
        search_advertiser=arguments.String(),
        unassigned=arguments.Boolean(),
        order=fields.String(),
        limit=fields.Int(),
        offset=fields.Int(),
        start_date=fields.String(),
        end_date=fields.String(),
        **constants.campaign_filters,
    )
    campaign_notifications = fields.ConnectionField(
        "CampaignNotificationConnection",
        id=arguments.UUID(required=True),
        not_notified_in_the_last_hours=arguments.Int(
            description="Filters influencers based on maximum amount of hours past since last notification sent"
        ),
    )
    campaigns_for_advertiser = fields.ConnectionField(
        "CampaignConnection", domain=arguments.String(required=True)
    )
    campaign_stats = fields.Field(
        "CampaignStats", region_id=arguments.UUID(required=False, description="Region ID")
    )
    campaign_influncer_targeting = fields.Field(
        fields.GenericScalar,
        campaign_id=arguments.UUID(required=True, description="The campaign ID"),
        username=arguments.String(required=True, description="The influencer username"),
    )

    @permissions.team_member.require()
    # @cached(ttl=dt.timedelta(hours=2))
    def resolve_campaign_stats(root, info, region_id=None):
        selection = {
            re.sub("([A-Z]+)", r"_\1", selection.name.value).lower(): True
            for selection in next(
                val for val in info.field_asts if val.name.value == "campaignStats"
            ).selection_set.selections
            if not selection.name.value.startswith("_")
        }
        region = Region.query.get(region_id) if region_id else None
        campaign_stats = CampaignStats(region)

        def get_val(val):
            if hasattr(val, "items"):
                return list(val.items())
            return val

        return {
            selection_name: get_val(getattr(campaign_stats, selection_name))
            for selection_name in selection
        }

    @permissions.manage_influencers.require()
    def resolve_campaign_notifications(root, info, id, not_notified_in_the_last_hours=None):
        campaign = get_campaign_or_404(id)
        notification_count = Influencer.notification_count(campaign)
        last_notification_sent = Influencer.last_notification_sent(campaign)
        query = (
            db.session.query(
                Influencer, Offer, Campaign, last_notification_sent, notification_count
            )
            .outerjoin(Offer, and_(Offer.influencer_id == Influencer.id, Offer.campaign_id == id))
            .filter(
                Influencer.is_eligible,
                Influencer.matches_targeting(campaign.targeting),
                Campaign.id == id,
            )
        )
        if not campaign.public:
            query = query.filter(Offer.id != None)
        if not_notified_in_the_last_hours is not None:
            now = dt.datetime.now(dt.timezone.utc)
            min_last_notification_date = now - dt.timedelta(hours=not_notified_in_the_last_hours)
            query = query.filter(
                or_(
                    Influencer.last_notification_sent(campaign) == None,
                    Influencer.last_notification_sent(campaign) < min_last_notification_date,
                )
            )
        return query.order_by(last_notification_sent.desc().nullslast(), Influencer.id)

    @permissions.public.require()
    def resolve_campaign(root, info, id):
        query = filter_campaigns()
        campaign = query.filter(Campaign.id == id).one_or_none()

        if campaign is None and current_user.role_name == "influencer":
            from takumi.gql.utils import get_public_campaign

            campaign = get_public_campaign(id)

        return campaign

    @permissions.public.require()
    def resolve_campaigns(
        root,
        info,
        region_id=None,
        mine=False,
        unassigned=False,
        search=None,
        search_advertiser=None,
        order=None,
        limit=0,
        offset=0,
        start_date=None,
        end_date=None,
        **filters,
    ):
        query = filter_campaigns()

        if start_date and end_date:
            query = filter_campaigns_by_date_range(start=start_date, end=end_date, query=query)

        if not permissions.edit_campaign.can() and not permissions.see_archived_campaigns.can():
            # Force filter. Only allow users that have permissions to archive campaigns to see archived campaigns
            filters["archived"] = False

        campaigns_with_current_region = filter_campaigns_by_region(query, region_id)
        mine_campaigns = filter_mine_campaigns(campaigns_with_current_region, mine)
        unassigned_campaigns = filter_unassigned_campaigns(mine_campaigns, unassigned)
        campaigns_with_current_name = filter_campaigns_by_search_string(
            unassigned_campaigns, search
        )
        filtered_campaigns_by_advertiser_name = filter_campaigns_by_advertiser_name(
            campaigns_with_current_name, search_advertiser
        )

        advertiser_industries_ids = filters.pop("advertiser_industries_ids", None)
        campaigns_with_current_industries = filter_campaigns_by_industry(
            filtered_campaigns_by_advertiser_name, advertiser_industries_ids
        )

        filtered_campaigns = filter_campaigns_by_campaign_filters(
            campaigns_with_current_industries, **filters
        )
        ordered_campaigns = sort_campaigns_by_order(filtered_campaigns, order)
        paginated_campaigns = paginate_query(ordered_campaigns, offset, limit)

        return paginated_campaigns

    @permissions.public.require()
    def resolve_campaigns_for_advertiser(root, info, domain):
        query = filter_campaigns()
        return query.filter(Advertiser.domain == domain).order_by(Campaign.created.desc())

    @permissions.manage_influencers.require()
    def resolve_campaign_influncer_targeting(root, info, campaign_id, username):
        campaign = get_campaign_or_404(campaign_id)
        influencer = get_influencer_or_404(username)
        targeting = campaign.targeting

        result = {
            **get_influencer_targeting_filters(targeting, influencer),
            "Brand cooldown": not campaign.advertiser.on_cooldown(influencer),
            "Eligible": influencer.is_eligible,
        }

        d = {key: bool(val) for key, val in result.items()}
        return OrderedDict(sorted(d.items()))
