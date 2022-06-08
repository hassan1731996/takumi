from flask import g
from flask_principal import Permission as _Permission

from takumi.roles import needs as need


class Permission(_Permission):
    """Our own "base" permission which always includes the developer_role need
    thus ensuring our developers have access to anything by default.
    """

    def __init__(self, *needs):
        needs = [need.developer_role, need.system_role] + list(needs)
        super().__init__(*needs)

    def can(self, *args, **kwargs):
        if not hasattr(g, "identity"):
            return False
        return super().can(*args, **kwargs)


class PublicPermission(_Permission):
    """A no-op permission that needs to be set to indicate no permission requirements in graphql"""

    pass


public = PublicPermission()

# Advertiser role access
advertiser_owner = Permission(need.advertiser_owner_access)
advertiser_admin = Permission(need.advertiser_owner_access, need.advertiser_admin_access)
advertiser_member = Permission(
    need.advertiser_owner_access,
    need.advertiser_admin_access,
    need.advertiser_member_access,
    need.access_all_advertisers,
)


# Role permissions
account_manager = Permission(need.account_manager_role)
campaign_manager = Permission(need.campaign_manager_role)
community_manager = Permission(need.community_manager_role)
developer = Permission()
influencer = Permission(need.influencer_role)
advertiser = Permission(need.advertiser_role)
team_member = Permission(need.team_member_role)
accounting = Permission(need.accounting_role)
hybrid_account_campaign_manager = Permission(need.hybrid_account_campaign_manager_role)

# Action permissions
access_all_advertisers = Permission(need.access_all_advertisers)
access_all_gigs = Permission(need.access_all_gigs)
access_all_influencers = Permission(need.access_all_influencers)
access_all_posts = Permission(need.access_all_posts)
access_all_regions = Permission(need.access_all_regions)
access_all_users = Permission(need.access_all_users)
access_sales_force = Permission(need.access_sales_force)
approve_gig = Permission(need.approve_gig)
archive_brand = Permission(need.archive_brand, need.advertiser_owner_access)
assign_campaign_manager = Permission(need.assign_campaign_manager)
assign_community_manager = Permission(need.assign_community_manager)
bypass_instagram_profile_validation = Permission(need.bypass_instagram_profile_validation)
campaigns_page_access = Permission(need.campaigns_page_access)
connect_facebook = Permission(need.connect_facebook)
create_brand = Permission(need.create_brand)
dashboard_page_access = Permission(need.dashboard_page_access)
dismiss_gig_report = Permission(need.dismiss_gig_report)
edit_campaign = Permission(need.edit_campaign)
get_enrollment_url = Permission(need.get_enrollment_url)
launch_campaign = Permission(need.launch_campaign)
link_gig = Permission(need.link_gig)
list_regions = Permission(need.list_regions)
manage_influencers = Permission(need.manage_influencers)
manage_payments = Permission(need.manage_payments)
manage_posts = Permission(need.manage_posts)
manage_tasks = Permission(need.manage_tasks)
mark_campaign_as_completed = Permission(need.mark_campaign_as_completed)
mark_product_as_in_transit = Permission(need.mark_product_as_in_transit)
preview_campaign = Permission(need.preview_campaign)
reject_gig = Permission(need.reject_gig)
remove_user_from_advertiser = Permission(need.remove_user_from_advertiser)
report_after_review_period = Permission(need.report_after_review_period)
report_gig = Permission(need.report_gig)
request_gig_resubmission = Permission(need.request_gig_resubmission)
review_gig = Permission(need.review_gig)
see_reported_gigs = Permission(need.see_reported_gigs)
see_archived_campaigns = Permission(need.see_archived_campaigns)
set_influencer_cooldown = Permission(need.set_influencer_cooldown)
super_admin = Permission(need.super_admin)
use_takumi_payment = Permission(need.use_takumi_payment)
view_influencer_info = Permission(need.view_influencer_info)
view_post_reports = Permission(need.view_post_reports)
view_brand_info = Permission(need.view_brand_info)

# Developer permissions
see_request_cost = Permission(need.see_request_cost)


# Granular resource permissions
def set_user_role(role_name):
    return Permission(need.set_user_role(role_name))
