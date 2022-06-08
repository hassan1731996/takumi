from tasktiger.exceptions import RetryException
from tasktiger.retry import fixed

from takumi.extensions import tiger
from takumi.ig.instascrape import InstascrapeUnavailable
from takumi.models import Influencer, Offer
from takumi.services import OfferService


@tiger.task(unique=True)
def update_influencer(influencer_id: str) -> None:
    from takumi.instagram_account import refresh_instagram_account

    influencer = Influencer.query.get_or_404(influencer_id)

    instagram_account = influencer.instagram_account
    if instagram_account is None:
        # XXX: Stop scheduling these
        return

    try:
        profile = refresh_instagram_account(instagram_account)
    except InstascrapeUnavailable:
        raise RetryException(method=fixed(delay=600, max_retries=5))

    if profile:
        # Update any offers that should be updated
        offers = Offer.query.filter(
            Offer.state.in_(
                [
                    Offer.STATES.ACCEPTED,
                    Offer.STATES.REQUESTED,
                    Offer.STATES.CANDIDATE,
                    Offer.STATES.APPROVED_BY_BRAND,
                ]
            ),
            ~Offer.is_claimable,
            Offer.influencer == influencer,
        )
        for offer in offers:
            if any(
                gig.instagram_post is not None
                or (gig.instagram_story is not None and gig.instagram_story.posted)
                for gig in offer.gigs
            ):
                # Only update followers per post if no content posted yet
                continue

            followers = instagram_account.followers

            if followers and offer.followers_per_post != followers:
                with OfferService(offer) as service:
                    service.set_followers_per_post(followers)
