import pytest

from takumi.models import Influencer, InstagramAccount, User


@pytest.fixture(scope="function")
def db_influencer_bob(db_session, db_interest, db_region):
    user = User(role_name="123")
    influencer = Influencer(
        state="verified",
        is_signed_up=True,
        interests=[db_interest],
        target_region=db_region,
        user=user,
    )
    instagram_account = InstagramAccount(
        ig_username="bob",
        ig_is_private=False,
        ig_user_id="123",
        ig_media_id="123",
        token="123",
        followers=20000,
        media_count=20000,
        influencer=influencer,
    )
    db_session.add(user)
    db_session.add(influencer)
    db_session.add(instagram_account)
    db_session.commit()
    return influencer


@pytest.fixture(scope="function")
def db_influencer_alice(db_session, db_interest, db_region):
    user = User(role_name="123")
    influencer = Influencer(
        state="verified",
        interests=[db_interest],
        target_region=db_region,
        is_signed_up=True,
        user=user,
    )
    instagram_account = InstagramAccount(
        ig_username="alice",
        ig_is_private=False,
        ig_user_id="1234",
        ig_media_id="1234",
        token="1234",
        followers=20000,
        media_count=20000,
        influencer=influencer,
    )
    db_session.add(user)
    db_session.add(influencer)
    db_session.add(instagram_account)
    db_session.commit()
    return influencer
