from takumi.gql import arguments, fields
from takumi.gql.utils import get_influencer_or_404, update_last_active
from takumi.models import Campaign
from takumi.roles import permissions


class InfluencerCampaignQuery:
    influencer_campaign = fields.Field(
        "InfluencerCampaignAndOffer",
        username=arguments.String(),
        id=arguments.UUID(),
        campaign_id=arguments.UUID(required=True),
    )

    influencer_campaigns = fields.ConnectionField(
        "InfluencerCampaignAndOfferConnection", username=arguments.String(), id=arguments.UUID()
    )

    targeted_campaigns = fields.ConnectionField(
        "InfluencerCampaignAndOfferConnection", username=arguments.String(), id=arguments.UUID()
    )

    requested_campaigns = fields.ConnectionField(
        "InfluencerCampaignAndOfferConnection", username=arguments.String(), id=arguments.UUID()
    )

    active_campaigns = fields.ConnectionField(
        "InfluencerCampaignAndOfferConnection", username=arguments.String(), id=arguments.UUID()
    )

    campaign_history = fields.ConnectionField(
        "InfluencerCampaignAndOfferConnection", username=arguments.String(), id=arguments.UUID()
    )

    revoked_or_rejected_campaigns = fields.ConnectionField(
        "InfluencerCampaignAndOfferConnection", username=arguments.String(), id=arguments.UUID()
    )

    expired_campaigns = fields.ConnectionField(
        "InfluencerCampaignAndOfferConnection", username=arguments.String(), id=arguments.UUID()
    )

    @permissions.public.require()
    def resolve_influencer_campaigns(root, info, username=None, id=None):
        influencer = get_influencer_or_404(id or username)
        if influencer:
            return influencer.campaigns

    @permissions.public.require()
    def resolve_influencer_campaign(root, info, campaign_id, username=None, id=None):
        influencer = get_influencer_or_404(id or username)
        if influencer:
            return influencer.campaigns.filter(Campaign.id == campaign_id).one_or_none()

    @permissions.public.require()
    def resolve_targeted_campaigns(root, info, username=None, id=None):
        influencer = get_influencer_or_404(id or username)
        if influencer:
            return influencer.targeted_campaigns

    @permissions.public.require()
    def resolve_requested_campaigns(root, info, username=None, id=None):
        influencer = get_influencer_or_404(id or username)
        if influencer:
            return influencer.requested_campaigns

    @permissions.public.require()
    @update_last_active
    def resolve_active_campaigns(root, info, username=None, id=None):
        influencer = get_influencer_or_404(id or username)
        if influencer:
            return influencer.active_campaigns

    @permissions.public.require()
    def resolve_campaign_history(root, info, username=None, id=None):
        influencer = get_influencer_or_404(id or username)
        if influencer:
            return influencer.campaign_history

    @permissions.public.require()
    def resolve_revoked_or_rejected_campaigns(root, info, username=None, id=None):
        influencer = get_influencer_or_404(id or username)
        if influencer:
            return influencer.revoked_or_rejected_campaigns

    @permissions.public.require()
    def resolve_expired_campaigns(root, info, username=None, id=None):
        influencer = get_influencer_or_404(id or username)
        if influencer:
            return influencer.expired_campaigns
