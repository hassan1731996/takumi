from typing import Dict, List

from flask_principal import Need, RoleNeed

from .needs import (
    access_all_advertisers,
    access_all_gigs,
    access_all_influencers,
    access_all_posts,
    access_all_regions,
    access_all_users,
    access_app_development_menu,
    access_sales_force,
    account_manager_role,
    accounting_role,
    advertiser_owner_access,
    advertiser_role,
    archive_brand,
    assign_campaign_manager,
    assign_community_manager,
    bypass_instagram_profile_validation,
    campaign_manager_role,
    campaigns_page_access,
    community_manager_role,
    connect_facebook,
    create_brand,
    dashboard_page_access,
    developer_role,
    dismiss_gig_report,
    edit_campaign,
    get_enrollment_url,
    hybrid_account_campaign_manager_role,
    influencer_role,
    launch_campaign,
    link_gig,
    list_regions,
    manage_influencers,
    manage_payments,
    manage_posts,
    mark_campaign_as_completed,
    mark_product_as_in_transit,
    preview_campaign,
    reject_gig,
    remove_user_from_advertiser,
    report_after_review_period,
    report_gig,
    request_gig_resubmission,
    review_gig,
    see_archived_campaigns,
    see_reported_gigs,
    send_recruitment_dm,
    set_influencer_cooldown,
    team_member_role,
    view_influencer_info,
    view_offer_reward_info,
    view_participants,
    view_post_reports,
)


class RoleType(type):
    """RoleType collects needs declared as static class variables,
    to allow for hierarchical user types which inherit needs.
    """

    def __new__(cls, name, bases, attrs):
        needs = set(attrs.pop("needs", []))

        for base in bases:
            needs.update(getattr(base, "needs", []))

        attrs["needs"] = needs

        return super().__new__(cls, name, bases, attrs)


class Role(metaclass=RoleType):
    def has_role(self, role_name):
        return RoleNeed(role_name) in self.needs


class AnonymousRole(Role):
    name: str = "anonymous"
    needs: List[Need] = []


class AdvertiserRole(Role):
    name: str = "advertiser"
    needs: List[Need] = [
        advertiser_role,
        access_all_regions,
        campaigns_page_access,
        dashboard_page_access,
        list_regions,
        preview_campaign,
        report_gig,
        connect_facebook,
        team_member_role,
        access_all_influencers,
        see_archived_campaigns,
    ]


class InfluencerRole(Role):
    name: str = "influencer"
    needs: List[Need] = [influencer_role, access_all_regions, view_offer_reward_info]


class CampaignManagerRole(Role):
    name: str = "campaign_manager"
    needs: List[Need] = [
        access_all_advertisers,
        access_all_gigs,
        access_all_influencers,
        access_all_posts,
        access_all_regions,
        access_all_users,
        access_app_development_menu,
        access_sales_force,
        advertiser_owner_access,
        archive_brand,
        advertiser_owner_access,  # give Campaign Managers blanket "owner" access to advertisers
        assign_campaign_manager,
        assign_community_manager,
        bypass_instagram_profile_validation,
        create_brand,
        account_manager_role,
        campaign_manager_role,
        community_manager_role,
        dismiss_gig_report,
        edit_campaign,
        get_enrollment_url,
        influencer_role,
        launch_campaign,
        link_gig,
        list_regions,
        manage_influencers,
        manage_posts,
        mark_campaign_as_completed,
        mark_product_as_in_transit,
        preview_campaign,
        reject_gig,
        remove_user_from_advertiser,
        report_after_review_period,
        report_gig,
        request_gig_resubmission,
        review_gig,
        see_reported_gigs,
        send_recruitment_dm,
        set_influencer_cooldown,
        team_member_role,
        view_influencer_info,
        view_offer_reward_info,
        view_participants,
        view_post_reports,
        hybrid_account_campaign_manager_role,
    ]


class CommunityManagerRole(CampaignManagerRole):
    name: str = "community_manager"


class AccountManagerRole(Role):
    name: str = "account_manager"
    needs: List[Need] = [
        access_all_advertisers,
        access_all_gigs,
        access_all_influencers,
        access_all_posts,
        access_all_regions,
        access_all_users,
        access_app_development_menu,
        access_sales_force,
        account_manager_role,
        advertiser_owner_access,
        archive_brand,
        bypass_instagram_profile_validation,
        create_brand,
        dismiss_gig_report,
        edit_campaign,
        get_enrollment_url,
        influencer_role,
        list_regions,
        manage_influencers,
        manage_posts,
        mark_campaign_as_completed,
        mark_product_as_in_transit,
        preview_campaign,
        remove_user_from_advertiser,
        report_after_review_period,
        report_gig,
        review_gig,
        see_reported_gigs,
        send_recruitment_dm,
        set_influencer_cooldown,
        team_member_role,
        view_influencer_info,
        view_offer_reward_info,
        view_participants,
        view_post_reports,
        hybrid_account_campaign_manager_role,
    ]


class AccountManagerLegacyRole(Role):
    name: str = "account_manager_legacy"
    needs: List[Need] = [
        access_all_advertisers,
        access_all_gigs,
        access_all_influencers,
        access_all_posts,
        access_all_regions,
        access_all_users,
        access_app_development_menu,
        access_sales_force,
        advertiser_owner_access,  # give Account Manager blanket "owner" access to advertisers
        bypass_instagram_profile_validation,
        create_brand,
        edit_campaign,
        get_enrollment_url,
        influencer_role,
        list_regions,
        manage_posts,
        preview_campaign,
        remove_user_from_advertiser,
        report_gig,
        set_influencer_cooldown,
        team_member_role,
        view_influencer_info,
        view_offer_reward_info,
        view_participants,
        view_post_reports,
    ]


class SalesDirectorRole(AccountManagerLegacyRole):
    name: str = "sales_director"


class HybridAccountCampaignManagerRole(AccountManagerRole, CampaignManagerRole):
    name: str = "hybrid_account_campaign_manager"


class DeveloperRole(Role):
    name: str = "developer"
    needs: List[Need] = [developer_role]


class AccountingRole(Role):
    """Role for Accounting back office staff.  Can manage everything except
    campaign specifics.  Can access payment information on offers, not available
    to other employees.
    """

    name: str = "accounting"
    needs: List[Need] = [
        access_all_advertisers,
        access_all_gigs,
        access_all_influencers,
        access_all_posts,
        access_all_regions,
        access_all_users,
        access_app_development_menu,
        access_sales_force,
        accounting_role,
        advertiser_owner_access,
        bypass_instagram_profile_validation,
        create_brand,
        edit_campaign,
        get_enrollment_url,
        influencer_role,
        list_regions,
        manage_influencers,
        manage_payments,
        preview_campaign,
        see_reported_gigs,
        team_member_role,
        view_influencer_info,
        view_offer_reward_info,
        view_participants,
    ]


class ReadOnlyMasterRole(Role):
    """A special read only role

    The role will only have access to everything that campaign managers and
    sales managers have access to, but through the authentication middleware
    will be prevented from making any mutations
    """

    name: str = "read_only_master"
    needs: List[Need] = [
        access_all_advertisers,
        access_all_gigs,
        access_all_influencers,
        access_all_posts,
        access_all_regions,
        access_all_users,
        access_app_development_menu,
        access_sales_force,
        advertiser_owner_access,
        archive_brand,
        assign_campaign_manager,
        assign_community_manager,
        bypass_instagram_profile_validation,
        campaign_manager_role,
        community_manager_role,
        create_brand,
        dismiss_gig_report,
        edit_campaign,
        get_enrollment_url,
        influencer_role,
        launch_campaign,
        link_gig,
        list_regions,
        manage_influencers,
        manage_posts,
        mark_campaign_as_completed,
        mark_product_as_in_transit,
        preview_campaign,
        reject_gig,
        remove_user_from_advertiser,
        report_after_review_period,
        report_gig,
        request_gig_resubmission,
        review_gig,
        see_reported_gigs,
        send_recruitment_dm,
        set_influencer_cooldown,
        team_member_role,
        view_influencer_info,
        view_offer_reward_info,
        view_participants,
        view_post_reports,
    ]


roles: Dict[str, Role] = {
    AccountManagerRole.name: AccountManagerRole(),
    AccountManagerLegacyRole.name: AccountManagerLegacyRole(),
    AccountingRole.name: AccountingRole(),
    AdvertiserRole.name: AdvertiserRole(),
    CampaignManagerRole.name: CampaignManagerRole(),
    CommunityManagerRole.name: CommunityManagerRole(),
    DeveloperRole.name: DeveloperRole(),
    ReadOnlyMasterRole.name: ReadOnlyMasterRole(),
    InfluencerRole.name: InfluencerRole(),
    SalesDirectorRole.name: SalesDirectorRole(),
    HybridAccountCampaignManagerRole.name: HybridAccountCampaignManagerRole(),
}
