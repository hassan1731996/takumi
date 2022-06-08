from typing import Optional

from sentry_sdk import capture_exception
from tasktiger.exceptions import RetryException
from tasktiger.retry import fixed

from core.facebook.instagram import InstagramError

from takumi.extensions import instascrape, tiger
from takumi.facebook_account import unlink_on_permission_error
from takumi.ig.instascrape import InstascrapeUnavailable, NotFound
from takumi.models import Gig
from takumi.models.post import PostTypes
from takumi.services.exceptions import CreateInstagramPostException


class NoInstagramAccount(Exception):
    pass


@tiger.task(unique=True)
def link_gig(gig_id: str, force: bool = False) -> Optional[str]:  # noqa: C901

    """Try to find a post by the influencer on instagram.com matching the gig

    Returns a simple status string depending on the success of the task, useful
    to report the status when invoking the task manually. Ignored when tiger
    workers run the task.
    """
    from takumi.models.influencer import FacebookPageDeactivated, MissingFacebookPage

    gig = Gig.query.get_or_404(gig_id)
    if gig.is_live and not force:
        # Gig has already been linked
        return None
    if gig.post.post_type in [PostTypes.tiktok, PostTypes.youtube]:
        return None

    # Check if we can find the post on their instagram
    try:
        influencer = gig.offer.influencer
        if influencer.instagram_account is None:
            raise NoInstagramAccount()
        if influencer.instagram_account.facebook_page is None:
            raise MissingFacebookPage()
        if not influencer.instagram_account.facebook_page.active:
            raise FacebookPageDeactivated()

        with unlink_on_permission_error(influencer.instagram_account.facebook_page):
            media = influencer.instagram_api.get_post_by_caption(
                gig.submission.caption, nocache=True
            )
    except (MissingFacebookPage, InstagramError, FacebookPageDeactivated, NoInstagramAccount) as e:
        if isinstance(e, InstagramError):
            capture_exception()
        try:
            media = instascrape.get_post_by_caption(
                gig.offer.influencer.username, gig.submission.caption, nocache=True
            )
        except NotFound:
            msg = "Influencer not found on instagram"
            return msg
        except InstascrapeUnavailable:
            # Try again later
            raise RetryException(method=fixed(delay=600, max_retries=5))

    if not media:
        # Not posted yet..
        return "Post not found on instagram"

    from takumi.services import InstagramPostService, OfferService

    media_id = media.get("ig_id", media["id"])

    try:
        InstagramPostService.create(gig.id, media_id)
    except CreateInstagramPostException as err:
        return f"Conditions not met: {err.errors}"

    if gig.offer.has_all_gigs():
        with OfferService(gig.offer) as service:
            service.last_gig_submitted()

    return "Gig linked"
