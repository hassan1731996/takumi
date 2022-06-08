from takumi.validation.offer import OfferValidator


def test_offer_validator_doesnt_raise_error_on_missing_gig_from_archived_post(
    post_factory, offer_factory, gig_factory, instagram_post_factory, db_campaign, db_session
):
    post = post_factory(campaign=db_campaign)
    archived_post = post_factory(campaign=db_campaign, archived=True)

    offer = offer_factory(campaign=db_campaign)

    gig = gig_factory(post=post, offer=offer, instagram_post=instagram_post_factory())

    db_session.add(post)
    db_session.add(archived_post)
    db_session.add(offer)
    db_session.add(gig)
    db_session.commit()

    OfferValidator(offer).validate()
