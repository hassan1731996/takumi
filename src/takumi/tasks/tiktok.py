from takumi import slack
from takumi.extensions import db, puppet, tiger
from takumi.models import Influencer, TikTokAccount
from takumi.utils import uuid4_str
from takumi.utils.tiktok import parse_username


@tiger.task()
def notify_new_tiktok(influencer_id: str, min_followers: int = 1000, min_likes: int = 1000) -> None:
    from takumi.services import TikTokAccountService
    from takumi.tasks.cdn import upload_media_to_cdn

    influencer = Influencer.query.get(influencer_id)

    if not influencer:
        return

    if not influencer.user.tiktok_username:
        return

    tiktok_username = parse_username(influencer.user.tiktok_username)
    if tiktok_username is None:
        return

    if influencer.user.tiktok_username != tiktok_username:
        influencer.user.tiktok_username = tiktok_username
        db.session.commit()

    user_response = puppet.get_user(tiktok_username)
    if user_response is None:
        return

    user_info = user_response["userInfo"]
    tiktok_profile = user_info["user"]
    if tiktok_profile is None:
        return

    account = TikTokAccount.query.filter(TikTokAccount.user_id == tiktok_profile["id"]).first()

    if "avatarLarger" in tiktok_profile:
        original_cover: str = tiktok_profile["avatarLarger"]
        if account is not None and account.original_cover != original_cover:
            cover = upload_media_to_cdn(original_cover, uuid4_str())
            tiktok_profile["avatarLarger"] = cover
    else:
        original_cover = ""

    # Update if exists
    if account is not None:
        with TikTokAccountService(account) as service:
            service.update(user_info, original_cover=original_cover)
    else:
        TikTokAccountService.create_tiktok_account(user_info, influencer=influencer)

    followers = user_info["stats"]["followerCount"]
    likes = user_info["stats"]["heartCount"]

    if followers < min_followers or likes < min_likes:
        return

    slack.notify_new_tiktok_signup(influencer, user_info)
