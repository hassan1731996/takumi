from functools import wraps
from typing import Optional

from core.facebook import FacebookRequestError, GraphAPIError
from core.facebook.ads import MAX_BATCH_SIZE

from takumi import slack
from takumi.constants import FACEBOOK_REVIEW_INSTAGRAM_ACCOUNT_ID, FACEBOOK_REVIEW_USER_ID
from takumi.error_codes import FACEBOOK_PAGE_NOT_FOUND_ERROR_CODE
from takumi.events.facebook_account import FacebookAccountLog
from takumi.events.facebook_page import FacebookPageLog
from takumi.extensions import db
from takumi.i18n import gettext as _
from takumi.models import (
    Advertiser,
    Config,
    FacebookAccount,
    FacebookAd,
    FacebookPage,
    InstagramAccount,
    User,
)
from takumi.services import Service
from takumi.services.exceptions import (
    AdvertiserNotLinkedToFacebookAccountException,
    FacebookException,
    FacebookNotLinkedException,
    FacebookPageNotFoundException,
    InfluencerNotFound,
    InstagramAccountNotFound,
    MissingGigImagesException,
    ServiceException,
)
from takumi.services.user import UserService
from takumi.tasks import facebook as facebook_tasks
from takumi.utils import uuid4_str


def facebook_method(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            return f(self, *args, **kwargs)
        except FacebookRequestError as e:
            error = e._body.get("error", {})
            msg = error.get("error_user_msg") or error.get("message") or "Facebook Error!"
            slack.facebook_notify_error(str(e))
            raise FacebookException(msg)

    return wrapper


def _facebook_review_authenticate() -> User:
    try:
        slack.notify_debug("Facebook review account authenticating")
    except Exception:
        pass

    user = User.query.get(FACEBOOK_REVIEW_USER_ID)
    instagram_account = InstagramAccount.query.get(FACEBOOK_REVIEW_INSTAGRAM_ACCOUNT_ID)

    user.facebook_account = instagram_account.facebook_page.facebook_account
    user.facebook_account.active = True
    user.influencer.instagram_account = instagram_account
    user.influencer._social_accounts_chosen = True

    db.session.commit()

    return user


def _unlink_review_account() -> User:
    user = User.query.get(FACEBOOK_REVIEW_USER_ID)
    user.facebook_account = None
    user.influencer._social_accounts_chosen = False
    user.influencer.instagram_account = None

    db.session.commit()

    return user


class FacebookService(Service):
    SUBJECT = FacebookAccount

    @staticmethod
    def authenticate(user_id: str, token: str) -> User:  # noqa: C901
        if user_id == FACEBOOK_REVIEW_USER_ID and Config.get("FACEBOOK_HARDCODE").value:
            # Manual handling of review user because it's impossible to provide
            # test users for the review
            return _facebook_review_authenticate()

        from takumi.events.user import UserLog
        from takumi.services import InfluencerService

        linking_events = []

        user = UserService.get_by_id(user_id)
        if user is None:
            raise ServiceException("User not found")

        influencer = user.influencer
        linking_events.append(f"Got {influencer.username}")

        try:
            user.facebook_account = FacebookAccount.by_token(token)
            user.facebook_account.active = True
            linking_events.append(f"Got account by token ({user.facebook_account})")
        except GraphAPIError as e:
            linking_events.append(f"Failed to get account by token ({str(e)})")
            UserLog(user).add_event("link_facebook_account_debug", {"messages": linking_events})
            db.session.commit()
            raise FacebookException(str(e))
        db.session.add(user)
        db.session.commit()

        facebook_account = user.facebook_account

        with FacebookService(user.facebook_account) as srv:
            srv.store_facebook_pages()

        facebook_pages = user.facebook_account.facebook_pages
        linking_events.append(f"User has {len(facebook_pages)} pages")
        if len(facebook_pages) == 0:
            linking_events.append("Raising because no pages found")
            UserLog(user).add_event("link_facebook_account_debug", {"messages": linking_events})
            db.session.commit()
            raise InstagramAccountNotFound(
                "No Facebook pages were found linked with your Facebook account. "
                'Make sure you have selected a page in "Edit Profile" in the Instagram app.'
            )

        instagram_accounts = [
            page.instagram_account for page in facebook_pages if page.instagram_account
        ]
        linking_events.append(f"User has {len(instagram_accounts)} accounts from the pages")

        # Unlink and raise error if no Instagram account found
        if len(instagram_accounts) == 0:
            linking_events.append("Raising because no account found")
            UserLog(user).add_event("link_facebook_account_debug", {"messages": linking_events})
            db.session.commit()
            raise InstagramAccountNotFound(
                "No Instagram account was found associated to any Facebook pages you have access to. "
                'Make sure you have selected a page in "Edit Profile" in the Instagram app.'
            )

        if influencer:
            if influencer.instagram_account is not None:
                # Remove the instagram_account they already have
                influencer.instagram_account = None

            # Auto link Instagram if only one Page provided
            if not influencer.instagram_account and len(instagram_accounts) == 1:
                linking_events.append("Auto linking because only one account")
                instagram_account = instagram_accounts[0]

                if instagram_account.influencer:
                    linking_events.append(
                        f"Account was already associated to {instagram_account.influencer}. Overwriting..."
                    )
                    instagram_account.influencer = influencer
                else:
                    linking_events.append("Instagram account wasn't associated to anyone")
                    instagram_account.influencer = influencer

                db.session.add(instagram_account)
                db.session.commit()

            if influencer.instagram_account:
                try:
                    with FacebookService(user.facebook_account) as fb_service:
                        fb_service.find_and_link_facebook_page(user_id)
                    with InfluencerService(user.influencer) as inf_service:
                        inf_service.fetch_and_save_audience_insights()
                except Exception as e:
                    linking_events.append(f"Raising on linking and insights: {str(e)}")
                    if user.influencer.username != "joemoidustein":  # Facebook Test User
                        UserLog(user).add_event(
                            "link_facebook_account_debug", {"messages": linking_events}
                        )
                        FacebookAccountLog(facebook_account).add_event(
                            "deactivate",
                            {
                                "facebook_user_id": facebook_account.facebook_user_id,
                                "permissions": facebook_account.permissions,
                                "facebook_page_ids": [
                                    p.page_id for p in facebook_account.facebook_pages
                                ],
                            },
                        )
                        facebook_account.revoke_permissions_on_facebook()
                        db.session.commit()
                        raise e

        UserLog(user).add_event(
            "link_facebook_account",
            {
                "facebook_user_id": facebook_account.facebook_user_id,
                "permissions": facebook_account.permissions,
                "facebook_page_ids": [p.page_id for p in facebook_account.facebook_pages],
            },
        )
        UserLog(user).add_event("link_facebook_account_debug", {"messages": linking_events})
        FacebookAccountLog(facebook_account).add_event(
            "activate",
            {
                "facebook_user_id": facebook_account.facebook_user_id,
                "permissions": facebook_account.permissions,
                "facebook_page_ids": [p.page_id for p in facebook_account.facebook_pages],
            },
        )
        db.session.commit()

        return user

    def store_facebook_pages(self):
        from takumi.services import InstagramAccountService
        from takumi.tasks.cdn import upload_instagram_account_profile_picture_to_cdn

        facebook_account = self.subject

        instagram_business_account_fields = ",".join(
            [
                "id",
                "ig_id",
                "username",
                "followers_count",
                "follows_count",
                "media_count",
                "biography",
                "profile_picture_url",
            ]
        )
        pages = facebook_account.graph_api.get_connections(
            id="me",
            connection_name="accounts?fields=instagram_business_account{"
            + instagram_business_account_fields
            + "},name,access_token",
        )["data"]

        for page in pages:
            instagram_business_account = page.get("instagram_business_account", {})
            business_account_id = instagram_business_account.get("id")
            if not business_account_id:
                continue

            facebook_page = next(
                (p for p in facebook_account.facebook_pages if p.page_id == page.get("id")), None
            ) or FacebookPage(page_id=page.get("id"), facebook_account=facebook_account)

            facebook_page.name = page.get("name")
            facebook_page.business_account_id = business_account_id
            facebook_page.page_access_token = page.get("access_token")
            facebook_page.active = True

            instagram_account = InstagramAccountService.get_by_ig_id(
                instagram_business_account.get("ig_id")
            )
            if not instagram_account:
                instagram_account = InstagramAccountService.create_instagram_account(
                    dict(
                        id=instagram_business_account.get("ig_id"),
                        username=instagram_business_account.get("username"),
                        is_private=False,
                        biography=instagram_business_account.get("biography"),
                        followers=instagram_business_account.get("followers_count"),
                        following=instagram_business_account.get("follows_count"),
                        media_count=instagram_business_account.get("media_count"),
                        profile_picture=instagram_business_account.get("profile_picture_url"),
                    )
                )
                upload_instagram_account_profile_picture_to_cdn.delay(
                    instagram_account_id=instagram_account.id,
                    image_url=instagram_account.profile_picture,
                )

            instagram_account.facebook_page = facebook_page

            db.session.add(instagram_account)
            db.session.add(facebook_page)

        db.session.commit()

    @staticmethod
    def unlink_facebook_account(user_id: str, reason: Optional[str] = None) -> User:
        if user_id == FACEBOOK_REVIEW_USER_ID and Config.get("FACEBOOK_HARDCODE").value:
            # Manual handling of review user because it's impossible to provide
            # test users for the review
            return _unlink_review_account()
        from takumi.events.user import UserLog

        user = UserService.get_by_id(user_id)
        if user is None:
            raise ServiceException("User not found")

        facebook_account = user.facebook_account
        if not facebook_account:
            raise FacebookNotLinkedException("You have not yet linked a Facebook account")

        facebook_account.users = [u for u in facebook_account.users if u.id != user_id]

        if facebook_account.users == []:
            facebook_account.revoke_permissions_on_facebook()

        UserLog(user).add_event(
            "unlink_facebook_account",
            {
                "facebook_user_id": facebook_account.facebook_user_id,
                "permissions": facebook_account.permissions,
                "facebook_page_ids": [p.page_id for p in facebook_account.facebook_pages],
                "reason": reason,
            },
        )

        if facebook_account.users == []:
            db.session.delete(facebook_account)
        elif user.influencer:
            if (
                user.influencer.instagram_account
                and user.influencer.instagram_account.facebook_page
            ):
                db.session.delete(user.influencer.instagram_account.facebook_page)
            user.influencer._social_accounts_chosen = False

        db.session.commit()

        return user

    def find_and_link_facebook_page(self, user_id):
        from takumi.tasks.cdn import upload_instagram_account_profile_picture_to_cdn

        facebook_account = self.subject
        user = next(user for user in facebook_account.users if user.id == user_id)
        influencer = user.influencer

        if not influencer:
            raise InfluencerNotFound("Influencer not found")

        instagram_account = influencer.instagram_account
        ig_user_id = instagram_account.ig_user_id

        if not ig_user_id:
            raise InstagramAccountNotFound("ig_user_id missing")

        pages = facebook_account.graph_api.get_connections(
            id="me",
            connection_name="accounts?fields=instagram_business_account{id, ig_id},name,access_token",
        )["data"]

        page = next(
            (
                p
                for p in pages
                if str(p.get("instagram_business_account", {}).get("ig_id", "")) == ig_user_id
            ),
            None,
        )

        if not page:
            try:
                FacebookService.unlink_facebook_account(user_id)
            finally:
                raise FacebookPageNotFoundException(
                    _(
                        'Could not find a Facebook Page associated with the Instagram account "%(username)s"',
                        username=influencer.username,
                    ),
                    error_code=FACEBOOK_PAGE_NOT_FOUND_ERROR_CODE,
                )

        facebook_page = next(
            (p for p in facebook_account.facebook_pages if p.page_id == page.get("id")), None
        ) or FacebookPage(page_id=page.get("id"), facebook_account=facebook_account)

        facebook_page.name = page.get("name")
        facebook_page.business_account_id = page.get("instagram_business_account", {}).get("id")
        facebook_page.page_access_token = page.get("access_token")
        facebook_page.active = True

        FacebookPageLog(facebook_page).add_event(
            "activate",
            {
                "facebook_user_id": facebook_page.facebook_account.facebook_user_id,
                "facebook_page_id": facebook_page.page_id,
                "business_account_id": facebook_page.business_account_id,
                "permissions": facebook_page.facebook_account.permissions,
            },
        )

        instagram_account.facebook_page = facebook_page
        instagram_account.ig_is_business_account = True

        # TODO: Remove this when we are officially multi-platform
        influencer._social_accounts_chosen = True

        db.session.add(facebook_account)
        db.session.commit()

        upload_instagram_account_profile_picture_to_cdn.delay(
            instagram_account_id=instagram_account.id,
            image_url=instagram_account.profile_picture,
        )

    # GET
    def get_takumi_ad_by_id(self, id):
        return FacebookAd.query.filter(
            FacebookAd.facebook_account == self.subject, FacebookAd.id == id
        ).one_or_none()

    @property
    def ads_api(self):
        return self.subject.ads_api

    @staticmethod
    def query_takumi_ad(account_id=None, campaign_id=None, adset_id=None, ad_id=None):
        query = FacebookAd.query.filter(FacebookAd.ad_id != None)  # noqa
        if account_id:
            query = query.filter(FacebookAd.account_id == account_id)
        if campaign_id:
            query = query.filter(FacebookAd.campaign_id == campaign_id)
        if adset_id:
            query = query.filter(FacebookAd.adset_id == adset_id)
        if ad_id:
            query = query.filter(FacebookAd.ad_id == ad_id)
        return query

    @facebook_method
    def get_ad_accounts(self):
        ad_accounts = [ad_account._json for ad_account in self.ads_api.get_ad_accounts()]
        for ad_account in ad_accounts:
            ad_account["takumi_creative"] = (
                self.query_takumi_ad(account_id=ad_account["id"]).count() > 0
            )
        return ad_accounts

    @facebook_method
    def get_campaigns(
        self, account_id, include_insights=False, page=0, per_page=None, only_takumi=False
    ):
        prefixed_account_id = f"act_{account_id}"

        campaigns = [campaign._json for campaign in self.ads_api.get_campaigns(prefixed_account_id)]

        for campaign in campaigns:
            campaign["takumi_creative"] = (
                self.query_takumi_ad(campaign_id=campaign["id"]).count() > 0
            )

        if only_takumi:
            campaigns = [campaign for campaign in campaigns if campaign["takumi_creative"]]

        if per_page or include_insights:
            per_page = min(per_page or MAX_BATCH_SIZE, MAX_BATCH_SIZE)
            campaigns = campaigns[page * per_page : (page + 1) * per_page]

        if include_insights:
            campaign_ids = [campaign["id"] for campaign in campaigns]
            insights = self.ads_api.get_campaigns_insights(campaign_ids)
            for campaign in campaigns:
                campaign.update(dict(insights=insights.get(campaign["id"], {})))

        return campaigns

    @facebook_method
    def get_adsets(
        self, campaign_id, include_insights=False, page=0, per_page=None, only_takumi=False
    ):
        adsets = [adset._json for adset in self.ads_api.get_ad_sets(campaign_id)]

        for adset in adsets:
            adset["takumi_creative"] = self.query_takumi_ad(adset_id=adset["id"]).count() > 0

        if only_takumi:
            adsets = [adset for adset in adsets if adset["takumi_creative"]]

        if per_page or include_insights:
            per_page = min(per_page or MAX_BATCH_SIZE, MAX_BATCH_SIZE)
            adsets = adsets[page * per_page : (page + 1) * per_page]

        if include_insights:
            adset_ids = [adset["id"] for adset in adsets]
            insights = self.ads_api.get_adsets_insights(adset_ids)
            for adset in adsets:
                adset.update(dict(insights=insights.get(adset["id"], {})))

        return adsets

    @facebook_method
    def get_ads(self, adset_id, include_insights=False, page=0, per_page=None, only_takumi=False):
        ads = [ad._json for ad in self.ads_api.get_ads(adset_id)]

        for ad in ads:
            ad["takumi_creative"] = self.query_takumi_ad(ad_id=ad["id"]).count() > 0

        if only_takumi:
            ads = [ad for ad in ads if ad["takumi_creative"]]

        if per_page or include_insights:
            per_page = min(per_page or MAX_BATCH_SIZE, MAX_BATCH_SIZE)
            ads = ads[page * per_page : (page + 1) * per_page]

        if include_insights:
            ad_ids = [ad["id"] for ad in ads]
            insights = self.ads_api.get_ads_insights(ad_ids)
            for ad in ads:
                ad.update(dict(insights=insights.get(ad["id"], {})))

        return ads

    @facebook_method
    def get_pages(self):
        pages = self.ads_api.get_pages()
        return [page._json for page in pages]

    @facebook_method
    def get_ad_account(self, ad_account_id):
        ad_account = self.ads_api.get_ad_account(ad_account_id)._json
        ad_account["takumi_creative"] = (
            self.query_takumi_ad(account_id=ad_account["id"]).count() > 0
        )
        return ad_account

    @facebook_method
    def get_campaign(self, campaign_id):
        campaign = self.ads_api.get_campaign(campaign_id)
        campaign_obj = campaign._json
        campaign_obj["takumi_creative"] = (
            self.query_takumi_ad(campaign_id=campaign_obj["id"]).count() > 0
        )
        campaign_obj["insights"] = self.ads_api.get_campaign_insights(campaign_id)
        return campaign_obj

    @facebook_method
    def get_adset(self, adset_id):
        adset = self.ads_api.get_ad_set(adset_id)
        adset_obj = adset._json
        adset_obj["insights"] = self.ads_api.get_adset_insights(adset_id)
        adset_obj["takumi_creative"] = self.query_takumi_ad(adset_id=adset_obj["id"]).count() > 0
        return adset_obj

    @facebook_method
    def get_ad(self, ad_id):
        ad = self.ads_api.get_ad(ad_id)
        ad_obj = ad._json
        ad_obj["insights"] = self.ads_api.get_ad_insights(ad_id)
        ad_obj["takumi_creative"] = self.query_takumi_ad(ad_id=ad["id"]).count() > 0
        return ad_obj

    @facebook_method
    def create_campaign(self, account_id, name, objective):
        return self.ads_api.create_campaign(account_id, name, objective)._json

    @facebook_method
    def create_adset(self, campaign_id, name, daily_budget):
        campaign = self.ads_api.get_campaign(campaign_id)
        ad_account_id = "act_{}".format(campaign["account_id"])
        return self.ads_api.create_ad_set(ad_account_id, campaign_id, name, daily_budget)._json

    @facebook_method
    def create_carousel(self, adset_id, page_id, name, url, gig_ids, use_url_in_images=False):
        if not gig_ids:
            raise MissingGigImagesException("At least 1 image needs to be provided")

        ad_set = self.ads_api.get_ad_set(adset_id)

        advertiser = Advertiser.query.filter(
            Advertiser.fb_ad_account_id == ad_set["account_id"]
        ).one_or_none()

        if not advertiser:
            raise AdvertiserNotLinkedToFacebookAccountException(
                "Advertiser not linked to this Ad Account"
            )

        fb_ad = FacebookAd(
            id=uuid4_str(),
            account_id=ad_set["account_id"],
            facebook_account=self.subject,
            gig_ids=gig_ids,
            campaign_id=ad_set["campaign_id"],
            adset_id=adset_id,
        )
        db.session.add(fb_ad)
        db.session.commit()

        facebook_tasks.create_carousel.delay(fb_ad.id, page_id, name, url, use_url_in_images)

        return fb_ad
