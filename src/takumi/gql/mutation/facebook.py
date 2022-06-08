from flask_login import current_user

from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_influencer_or_404
from takumi.ig.profile import refresh_on_interval
from takumi.roles import permissions
from takumi.services import FacebookService, InfluencerService


class FacebookLogin(Mutation):
    class Arguments:
        token = arguments.String(required=True, description="Token provided by Facebook")

    current_user = fields.Field("User")

    @permissions.public.require()
    def mutate(root, info, token):
        user = FacebookService.authenticate(current_user.id, token)
        return FacebookLogin(current_user=user, ok=True)


class LinkInstagramAccount(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="Instagram Account ID")

    current_user = fields.Field("User")

    @permissions.influencer.require()
    def mutate(root, info, id):
        user = current_user
        influencer = user.influencer
        facebook_account = user.facebook_account

        if influencer.instagram_account:
            raise MutationException("You have already linked an Instagram account")

        if not facebook_account:
            raise MutationException("Facebook Account not linked")

        facebook_pages = facebook_account.facebook_pages
        instagram_accounts = [page.instagram_account for page in facebook_pages]

        try:
            instagram_account = next(igacc for igacc in instagram_accounts if igacc.id == id)
        except StopIteration:
            raise MutationException("Instagram Account not found")

        if instagram_account.influencer and instagram_account.influencer.is_signed_up:
            raise MutationException("Instagram Account already linked to another influencer")

        influencer.instagram_account = instagram_account
        db.session.add(influencer)
        db.session.commit()

        refresh_on_interval(influencer)

        with InfluencerService(current_user.influencer) as srv:
            srv.fetch_and_save_audience_insights()

        return LinkInstagramAccount(current_user=influencer.user, ok=True)


class FacebookLogout(Mutation):
    class Arguments:
        influencer_id = arguments.UUID(required=False, description="Influencer Account ID")
        unlink_instagram_account = arguments.Boolean(default_value=False)

    current_user = fields.Field("User")

    @permissions.influencer.require()
    def mutate(root, info, influencer_id=None, unlink_instagram_account=False):

        if influencer_id is not None:
            influencer = get_influencer_or_404(influencer_id)
            user = FacebookService.unlink_facebook_account(influencer.user_id)
        else:
            user = FacebookService.unlink_facebook_account(current_user.id)

        if False and unlink_instagram_account:
            instagram_account = user.influencer.instagram_account
            instagram_account.influencer = None
            db.session.add(instagram_account)
            db.session.commit()

        return FacebookLogout(current_user=user, ok=True)


class CreateFacebookCampaign(Mutation):
    class Arguments:
        ad_account_id = arguments.String(required=True, description="Ad Account ID")
        name = arguments.String(required=True, description="Campaign name")
        objective = arguments.String(required=True, description="Campaign objective")

    facebook_campaign = fields.Field("FacebookCampaign")

    @permissions.public.require()
    def mutate(root, info, ad_account_id, name, objective):
        facebook_campaign = FacebookService(current_user.facebook_account).create_campaign(
            ad_account_id, name, objective
        )
        return CreateFacebookCampaign(facebook_campaign=facebook_campaign, ok=True)


class CreateFacebookAdSet(Mutation):
    class Arguments:
        facebook_campaign_id = arguments.String(required=True, description="Facebook Campaign ID")
        name = arguments.String(required=True, description="AdSet name")
        daily_budget = arguments.Int(required=True, description="Daily budget")

    facebook_adset = fields.Field("FacebookAdSet")

    @permissions.public.require()
    def mutate(root, info, facebook_campaign_id, name, daily_budget):
        facebook_adset = FacebookService(current_user.facebook_account).create_adset(
            facebook_campaign_id, name, daily_budget
        )
        return CreateFacebookAdSet(facebook_adset=facebook_adset, ok=True)


class CreateFacebookCarousel(Mutation):
    class Arguments:
        adset_id = arguments.String(required=True, description="Facebook AdSet ID")
        page_id = arguments.String(required=True, description="Facebook Page ID")
        name = arguments.String(required=True, description="Carousel name")
        url = arguments.String(required=True, description="Carousel URL")
        gig_ids = arguments.List(arguments.UUID, required=True)
        use_url_in_images = arguments.Boolean(description="Use URL in Images")

    takumi_ad = fields.Field("FacebookTakumiAd")

    @permissions.public.require()
    def mutate(root, info, adset_id, page_id, name, url, gig_ids, use_url_in_images=True):
        takumi_ad = FacebookService(current_user.facebook_account).create_carousel(
            adset_id, page_id, name, url, gig_ids, use_url_in_images
        )
        return CreateFacebookCarousel(takumi_ad=takumi_ad, ok=True)


class FacebookMutation:
    facebook_login = FacebookLogin.Field()
    link_instagram_account = LinkInstagramAccount.Field()
    facebook_logout = FacebookLogout.Field()
    create_facebook_campaign = CreateFacebookCampaign.Field()
    create_facebook_adset = CreateFacebookAdSet.Field()
    create_facebook_carousel = CreateFacebookCarousel.Field()
