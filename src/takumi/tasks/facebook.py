import os

import requests

from core.facebook import FacebookRequestError

from takumi import slack
from takumi.extensions import db, tiger
from takumi.models import FacebookAd, Gig
from takumi.utils import uuid4_str


def download_file(url, destination):
    with requests.get(url, stream=True) as r:
        assert r.status_code == 200
        with open(destination, "wb") as f:
            for chunk in r:
                f.write(chunk)


@tiger.task(unique=True)
def create_carousel(ad_id, page_id, name, url, use_url_in_images=False):
    try:
        fb_ad = FacebookAd.query.get(ad_id)
        facebook_account = fb_ad.facebook_account
        ads_api = facebook_account.ads_api
        ad_set = ads_api.get_ad_set(fb_ad.adset_id)
        unprefixed_account_id = ad_set["account_id"]
        account_id = f"act_{unprefixed_account_id}"

        carousel_media = []
        tmp_filenames = []
        for gig_id in fb_ad.gig_ids:
            gig = Gig.query.get(gig_id)
            instagram_post = gig.instagram_post
            first_media = instagram_post.media[0]
            tmp_filename = f"/tmp/{uuid4_str()}.jpg"
            tmp_filenames.append(tmp_filename)
            download_file(first_media.url, tmp_filename)
            image_hash = ads_api.upload_image(account_id, tmp_filename).get_hash()

            if use_url_in_images:
                media_url = url
            else:
                media_url = instagram_post.link

            description = f"Photo by @{gig.offer.influencer.username}"

            carousel_media.append((image_hash, media_url, description))

        ad = ads_api.create_carousel_ad(
            account_id, ad_set.get_id_assured(), name, page_id, carousel_media, url
        )

        fb_ad.ad_id = ad["id"]
    except FacebookRequestError as e:
        error = e._body.get("error", {})
        msg = error.get("error_user_msg") or error.get("message") or "Facebook Error!"
        slack.facebook_notify_error(str(e))
        fb_ad.error = msg
    finally:
        for filename in tmp_filenames:
            try:
                os.remove(filename)
            except OSError:
                pass

    db.session.add(fb_ad)
    db.session.commit()
