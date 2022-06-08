import mock

from takumi.models import Offer
from takumi.tasks.influencer.update import update_influencer


def test_update_influencer_sets_followers_on_offers_if_not_active(
    db_influencer, offer_factory, gig_factory, instagram_post_factory
):
    db_influencer.instagram_account.followers = 5500

    offer_new = offer_factory(
        influencer=db_influencer, state=Offer.STATES.ACCEPTED, followers_per_post=5000
    )
    offer_in_progress = offer_factory(
        influencer=db_influencer, state=Offer.STATES.ACCEPTED, followers_per_post=5100
    )
    gig = gig_factory(offer=offer_in_progress)
    instagram_post_factory(gig=gig)

    with mock.patch("takumi.instagram_account.refresh_instagram_account"):
        update_influencer(db_influencer.id)

    assert offer_new.followers_per_post == 5500  # Updated
    assert offer_in_progress.followers_per_post == 5100  # Unchanged
