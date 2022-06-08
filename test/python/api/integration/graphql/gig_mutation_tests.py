import pytest

from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.gig import SubmitMedia
from takumi.models.offer import STATES as OFFER_STATES


class Media:
    def __init__(self, **entries):
        self.__dict__.update(entries)


def test_submit_media_mutation(client, db_influencer_user, db_offer, db_campaign, db_post):
    caption = "Whoa there"
    media = [
        {"type": "image", "url": "http://image"},
        {"type": "video", "url": "http://video", "thumbnail": None},
    ]

    db_offer.state = OFFER_STATES.ACCEPTED
    assert len(db_offer.gigs) == 0

    with client.user_request_context(db_influencer_user):
        SubmitMedia().mutate("info", media=media, caption=caption, post_id=db_post.id)

    assert len(db_offer.gigs) == 1

    gig = db_offer.gigs[0]
    media = gig.submission.media

    assert len(media) == 2

    assert media[0].type == "image"
    assert media[0].url == "http://image"

    assert media[1].type == "video"
    assert media[1].url == "http://video"


def test_submit_media_doesnt_leave_malformed_gig_after_invalid_submit(
    client, db_session, db_influencer_user, db_offer, db_campaign, db_post
):
    db_post.start_first_hashtag = True
    db_post.conditions = [{"type": "hashtag", "value": "ad"}]
    db_offer.state = OFFER_STATES.ACCEPTED
    db_session.commit()

    media = [{"type": "image", "url": "http://image"}]

    assert len(db_offer.gigs) == 0

    with pytest.raises(MutationException, match="Caption is invalid"):
        with client.user_request_context(db_influencer_user):
            SubmitMedia().mutate(
                "info", media=media, caption="Hashtag at end #ad", post_id=db_post.id
            )

    assert len(db_offer.gigs) == 0

    with client.user_request_context(db_influencer_user):
        SubmitMedia().mutate(
            "info", media=media, caption="#ad please don't fine me", post_id=db_post.id
        )

    assert len(db_offer.gigs) == 1

    gig = db_offer.gigs[0]
    assert gig.submission is not None
