from functools import partial

from flask_principal import ActionNeed, Need, RoleNeed

# General action needs
access_all_advertisers = ActionNeed("access_all_advertisers")
access_all_gigs = ActionNeed("access_all_gigs")
access_all_influencers = ActionNeed("access_all_influencers")
access_all_posts = ActionNeed("access_all_posts")
access_all_regions = ActionNeed("access_all_regions")
access_all_users = ActionNeed("access_all_users")
access_app_development_menu = ActionNeed("access_app_development_menu")
access_sales_force = ActionNeed("access_sales_force")
approve_gig = ActionNeed("approve_gig")
archive_brand = ActionNeed("archive_brand")
assign_campaign_manager = ActionNeed("assign_campaign_manager")
assign_community_manager = ActionNeed("assign_community_manager")
bypass_instagram_profile_validation = ActionNeed("bypass_instagram_profile_validation")
campaigns_page_access = ActionNeed("campaigns_page_access")
connect_facebook = ActionNeed("connect_facebook")
create_brand = ActionNeed("create_brand")
dashboard_page_access = ActionNeed("dashboard_page_access")
dismiss_gig_report = ActionNeed("dismiss_gig_report")
edit_campaign = ActionNeed("edit_campaign")
get_enrollment_url = ActionNeed("get_enrollment_url")
launch_campaign = ActionNeed("launch_campaign")
link_gig = ActionNeed("link_gig")
list_regions = ActionNeed("list_regions")
manage_influencers = ActionNeed("manage_influencers")
manage_payments = ActionNeed("manage_payments")
manage_posts = ActionNeed("manage_posts")
manage_tasks = ActionNeed("manage_tasks")
mark_campaign_as_completed = ActionNeed("mark_campaign_as_completed")
mark_product_as_in_transit = ActionNeed("mark_product_as_in_transit")
preview_campaign = ActionNeed("preview_campaign")
reject_gig = ActionNeed("reject_gig")
remove_user_from_advertiser = ActionNeed("remove_user_from_advertiser")
report_after_review_period = ActionNeed("report_after_review_period")
report_gig = ActionNeed("report_gig")
request_gig_resubmission = ActionNeed("request_gig_resubmission")
review_gig = ActionNeed("review_gig")
see_reported_gigs = ActionNeed("see_reported_gigs")
see_archived_campaigns = ActionNeed("see_archived_campaigns")
send_recruitment_dm = ActionNeed("send_recruitment_dm")
set_influencer_cooldown = ActionNeed("set_influencer_cooldown")
super_admin = ActionNeed("super_admin")
use_takumi_payment = ActionNeed("use_takumi_payment")
view_influencer_info = ActionNeed("view_influencer_info")
view_offer_reward_info = ActionNeed("view_offer_reward_info")
view_participants = ActionNeed("view_participants")
view_post_reports = ActionNeed("view_post_reports")
view_brand_info = ActionNeed("view_brand_info")

# Roles
account_manager_role = RoleNeed("account_manager")
developer_role = RoleNeed("developer")
system_role = RoleNeed("system")
campaign_manager_role = RoleNeed("campaign_manager")
community_manager_role = RoleNeed("community_manager")
influencer_role = RoleNeed("influencer")
accounting_role = RoleNeed("accounting")
advertiser_role = RoleNeed("advertiser")  # advertiser access / brand-user (XXX: refactor with Oli?)
team_member_role = RoleNeed("team_member")
hybrid_account_campaign_manager_role = RoleNeed("hybrid_account_campaign_manager")


# Advertiser/Brand access
advertiser_member_access = RoleNeed("advertiser_member")
advertiser_admin_access = RoleNeed("advertiser_admin")
advertiser_owner_access = RoleNeed("advertiser_owner")


# Granular resource protection needs
set_user_role = partial(Need, "set_user_role")


# Developer permissions
see_request_cost = ActionNeed("see_request_cost")
