import datetime as dt

from takumi.constants import INDUSTRY_CHOICES
from takumi.events import Event, EventApplicationException, TableLog
from takumi.models import CampaignEvent
from takumi.models.campaign import STATES


class CampaignLaunchValidationException(EventApplicationException):
    pass


class CampaignCreate(Event):
    def apply(self, campaign):
        campaign.state = STATES.DRAFT
        campaign.market_slug = self.properties["market_slug"]
        campaign.reward_model = self.properties["reward_model"]
        campaign.brand_match = self.properties["brand_match"]
        campaign.units = self.properties["units"]
        campaign.price = self.properties["price"]
        campaign.list_price = self.properties["list_price"]
        campaign.shipping_required = self.properties["shipping_required"]
        campaign.require_insights = self.properties["require_insights"]

        campaign.custom_reward_units = self.properties["custom_reward_units"]

        campaign.name = self.properties["name"]
        campaign.pictures = self.properties["pictures"]

        campaign.owner_id = self.properties["owner_id"]
        campaign.prompts = self.properties["prompts"]
        campaign.campaign_manager_id = self.properties["campaign_manager_id"]
        campaign.secondary_campaign_manager_id = self.properties["secondary_campaign_manager_id"]
        campaign.community_manager_id = self.properties["community_manager_id"]
        campaign.has_nda = self.properties["has_nda"]
        campaign.brand_safety = self.properties["brand_safety"]
        campaign.extended_review = self.properties["extended_review"]
        campaign.industry = self.properties["industry"]

        campaign.advertiser_id = self.properties["advertiser_id"]
        campaign.timezone = self.properties["timezone"]
        campaign.tags = self.properties["tags"]

        campaign.opportunity_product_id = self.properties["opportunity_product_id"]
        campaign.pro_bono = self.properties["pro_bono"]

        # XXX: Legacy
        campaign.description = self.properties.get("description")


class CampaignComplete(Event):
    start_state = STATES.LAUNCHED
    end_state = STATES.COMPLETED

    def apply(self, campaign):
        """This event is only used to log when a campaign is completed"""
        pass


class CampaignFullyReserved(Event):
    start_state = STATES.LAUNCHED

    def apply(self, campaign):
        campaign.full = True


class CampaignNotFullyReserved(Event):
    start_state = STATES.LAUNCHED

    def apply(self, campaign):
        campaign.full = False


class CampaignLaunch(Event):
    start_state = STATES.DRAFT
    end_state = STATES.LAUNCHED

    def _validate_campaign(self, campaign):
        """Raise an APIError if the campaign is invalid for launching"""
        if campaign.name is None or len(campaign.name) == 0:
            raise CampaignLaunchValidationException("Campaign name is missing")

        if len(campaign.pictures) == 0:
            raise CampaignLaunchValidationException("Campaign is missing pictures")

        if len(campaign.targeting.regions) == 0:
            raise CampaignLaunchValidationException("Campaign is missing regions")

        if not campaign.posts:
            raise CampaignLaunchValidationException("Campaign has no posts")

        if not all(post.brief for post in campaign.posts):
            raise CampaignLaunchValidationException("Campaign posts missing briefs")

    def apply(self, campaign):
        self._validate_campaign(campaign)
        campaign.started = dt.datetime.now(dt.timezone.utc)
        # Trigger scheduler-callback loop for a launched campaign
        campaign.media_updating = True


class StashCampaign(Event):
    start_state = (STATES.DRAFT, STATES.LAUNCHED)
    end_state = STATES.STASHED

    def apply(self, campaign):
        pass


class RestoreCampaign(Event):
    start_state = STATES.STASHED
    end_state = STATES.DRAFT

    def apply(self, campaign):
        pass


class SetUnits(Event):
    def apply(self, campaign):
        campaign.units = self.properties["units"]


class SetShippingRequired(Event):
    def apply(self, campaign):
        campaign.shipping_required = self.properties["shipping_required"]


class SetPushNotificationMessage(Event):
    def apply(self, campaign):
        campaign.push_notification_message = self.properties["push_notification_message"]


class SetName(Event):
    def apply(self, campaign):
        campaign.name = self.properties["name"]


class SetOpportunityProductId(Event):
    def apply(self, campaign):
        campaign.opportunity_product_id = self.properties["opportunity_product_id"]


class SetDescription(Event):
    def apply(self, campaign):
        campaign.description = self.properties["description"]


class SetPictures(Event):
    def apply(self, campaign):
        campaign.pictures = self.properties["pictures"]


class SetPrompts(Event):
    def apply(self, campaign):
        campaign.prompts = self.properties["prompts"]


class SetBrandSafety(Event):
    def apply(self, campaign):
        campaign.brand_safety = self.properties["brand_safety"]


class SetApplyFirst(Event):
    def apply(self, campaign):
        campaign.apply_first = self.properties["apply_first"]
        if not campaign.apply_first:
            campaign.brand_match = False


class SetBrandMatch(Event):
    def apply(self, campaign):
        campaign.brand_match = self.properties["brand_match"]


class SetExtendedReview(Event):
    def apply(self, campaign):
        campaign.extended_review = self.properties["extended_review"]


class SetOwner(Event):
    def apply(self, campaign):
        campaign.owner_id = self.properties["owner_id"]


class SetCampaignManager(Event):
    def apply(self, campaign):
        campaign.campaign_manager_id = self.properties["campaign_manager_id"]


class SetSecondaryCampaignManager(Event):
    def apply(self, campaign):
        campaign.secondary_campaign_manager_id = self.properties["secondary_campaign_manager_id"]


class SetCommunityManager(Event):
    def apply(self, campaign):
        campaign.community_manager_id = self.properties["community_manager_id"]


class SetHasNda(Event):
    def apply(self, campaign):
        campaign.has_nda = self.properties["has_nda"]


class SetIndustry(Event):
    def apply(self, campaign):
        industry = self.properties["industry"]
        if industry != "" and industry not in INDUSTRY_CHOICES:
            raise EventApplicationException(f'"{industry}" is not a valid industry')
        if isinstance(industry, str) and len(industry):
            campaign.industry = industry
        else:
            campaign.industry = None


class SetPublic(Event):
    def apply(self, campaign):
        campaign.public = self.properties["public"]


class SetProBono(Event):
    def apply(self, campaign):
        campaign.pro_bono = self.properties["pro_bono"]


class SetReportToken(Event):
    def apply(self, campaign):
        campaign.report_token = self.properties["new_token"]


class SetCustomRewardUnits(Event):
    def apply(self, campaign):
        campaign.custom_reward_units = self.properties["custom_reward_units"]


class SetPrice(Event):
    def apply(self, campaign):
        campaign.price = self.properties["price"]


class SetListPrice(Event):
    def apply(self, campaign):
        campaign.list_price = self.properties["list_price"]


class SetTags(Event):
    def apply(self, campaign):
        campaign.tags = self.properties["tags"]


class SetRequireInsights(Event):
    def apply(self, campaign):
        campaign.require_insights = self.properties["require_insights"]


class SetReportSummary(Event):
    def apply(self, campaign):
        campaign.report_summary = self.properties["summary"]


class CampaignLog(TableLog):
    event_model = CampaignEvent
    relation = "campaign"
    type_map = {
        "create": CampaignCreate,
        "launch": CampaignLaunch,
        "complete": CampaignComplete,
        "full": CampaignFullyReserved,
        "not_full": CampaignNotFullyReserved,
        "stash": StashCampaign,
        "restore": RestoreCampaign,
        "set_brand_safety": SetBrandSafety,
        "set_brand_match": SetBrandMatch,
        "set_apply_first": SetApplyFirst,
        "set_campaign_manager": SetCampaignManager,
        "set_secondary_campaign_manager": SetSecondaryCampaignManager,
        "set_community_manager": SetCommunityManager,
        "set_custom_reward_units": SetCustomRewardUnits,
        "set_description": SetDescription,
        "set_extended_review": SetExtendedReview,
        "set_has_nda": SetHasNda,
        "set_industry": SetIndustry,
        "set_list_price": SetListPrice,
        "set_name": SetName,
        "set_opportunity_product_id": SetOpportunityProductId,
        "set_owner": SetOwner,
        "set_pictures": SetPictures,
        "set_price": SetPrice,
        "set_prompts": SetPrompts,
        "set_public": SetPublic,
        "set_pro_bono": SetProBono,
        "set_push_notification_message": SetPushNotificationMessage,
        "set_report_summary": SetReportSummary,
        "set_report_token": SetReportToken,
        "set_require_insights": SetRequireInsights,
        "set_shipping_required": SetShippingRequired,
        "set_tags": SetTags,
        "set_units": SetUnits,
    }
