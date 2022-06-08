import datetime as dt

import mock
import pytest

from takumi.gql.generator import QueryGenerator
from takumi.gql.types import Influencer as InfluencerGQLType
from takumi.models import EmailLogin, Interest, User
from takumi.search.influencer import (
    IndexingError,
    InfluencerIndex,
    InfluencerSearch,
    update_influencer_info,
)
from takumi.utils import uuid4_str


@pytest.fixture(autouse=True)
def disable_refresh_instagram_account(monkeypatch):
    monkeypatch.setattr("takumi.gql.query.influencer.refresh_on_interval", mock.Mock())


def test_influencer_info_get_source_document(db_session, db_influencer):
    doc = InfluencerIndex.get_source_document(db_influencer.id)
    assert doc["influencer"]["id"] == db_influencer.id


def _try_to_get_field(obj, field):
    if isinstance(field, dict):
        rootkey = list(field)[0]
        subobj = getattr(obj, rootkey)
        if subobj is None:
            return
        subkeys = list(field.values())[0]
        for subkey in subkeys:
            _try_to_get_field(subobj, subkey)
    elif isinstance(obj, list):
        for el in obj:
            _try_to_get_field(el, field)
    else:
        try:
            getattr(obj, field)
        except AttributeError as e:
            try:
                obj[field]
            except KeyError:
                raise e


def test_influencer_info_contains_all_fields(db_session, elasticsearch, db_influencer):
    update_influencer_info(db_influencer.id)
    elasticsearch.indices.refresh()
    influencer_fields = QueryGenerator.extract_fields(InfluencerGQLType)

    rs = InfluencerSearch().get(db_influencer.id)
    for field in influencer_fields:
        try:
            _try_to_get_field(rs, field)
        except AttributeError:
            pytest.fail("field is missing or corrupted: {}".format(field))


def test_influencer_info_get_source_document_raises_indexerror(db_session):
    with pytest.raises(IndexingError) as exc:
        InfluencerIndex.get_source_document("this-is-not-a-valid-uuid-string")
    assert "badly formed" in str(exc.value.errors[0])


def test_influencer_update_hook_on_influencer_model_update(db_session, db_influencer, monkeypatch):
    mock_update_influencer_info = mock.Mock()
    monkeypatch.setattr(
        "takumi.search.influencer.indexing.update_influencer_info", mock_update_influencer_info
    )
    db_influencer.modified = dt.datetime.now(dt.timezone.utc)
    db_session.add(db_influencer)
    db_session.commit()
    assert mock_update_influencer_info.delay.called


def test_influencer_update_hook_on_instagram_account_model_update(
    db_session, db_instagram_account, db_influencer, monkeypatch
):
    mock_update_influencer_info = mock.Mock()
    monkeypatch.setattr(
        "takumi.search.influencer.indexing.update_influencer_info", mock_update_influencer_info
    )
    db_instagram_account.modified = dt.datetime.now(dt.timezone.utc)
    db_session.add(db_instagram_account)
    db_session.commit()
    assert mock_update_influencer_info.delay.called


def test_influencer_update_hook_on_influencer_model_insert(
    db_session, influencer_factory, instagram_account, monkeypatch
):
    new_influencer = influencer_factory(instagram_account=instagram_account)
    mock_update_influencer_info = mock.Mock()
    monkeypatch.setattr(
        "takumi.search.influencer.indexing.update_influencer_info", mock_update_influencer_info
    )
    db_session.add(new_influencer)
    db_session.commit()
    assert mock_update_influencer_info.delay.called


def test_influencer_update_from_source(db_influencer):
    with mock.patch("takumi.search.influencer.indexing.elasticsearch") as mock_elasticsearch:
        update_influencer_info(db_influencer.id)
        assert mock_elasticsearch.index.called


@pytest.fixture(scope="function")
def multiple_influencers(
    elasticsearch, tiger_task, instagram_account_factory, influencer_factory, db_session, db_region
):
    influencers = [
        ("mockymock", "jabbermocky@ponty-mocky-mython.co.uk"),
        ("markymark", "mark@mockberg.toplevel"),
        ("markymock", "mock@markberg.toplevel"),
        ("mockofbrian", "brian@barabas-rules-the-roost.edu"),
    ]
    ret = []
    for username, email in influencers:
        ig_account = instagram_account_factory(
            ig_username=username,
            ig_user_id=username,
            ig_media_id=username,
            token=username,
            ig_biography=email,
        )
        user = User(id=uuid4_str(), full_name=username, role_name="influencer")
        email = EmailLogin.create(email=email, password="mockmock", user=user)
        influencer = influencer_factory(
            instagram_account=ig_account, state="verified", target_region=db_region, user=user
        )
        db_session.add_all([user, influencer, email, ig_account])
        ret.append(influencer)
    db_session.commit()
    tiger_task.run_tasks([update_influencer_info])
    elasticsearch.indices.refresh()
    yield ret


def test_influencer_search_by_email(elasticsearch, db_session, db_influencer, multiple_influencers):
    difficult_email = "this_email_shares_a_domain_with_another@barabas-rules-the-roost.edu"
    db_influencer.user.email_login.email = difficult_email
    db_session.commit()

    db_influencer.instagram_account.ig_biography = (
        "this_email_shares_a_domain_with_anothe2r@barabas-rules-the-roost.edu"
    )
    update_influencer_info(db_influencer.id)
    elasticsearch.indices.refresh()

    rs = InfluencerSearch().search(difficult_email)
    doc = rs.first()
    assert rs.count() == 1
    assert doc.email == difficult_email

    rs = InfluencerSearch().search("barabas")
    assert rs.count() == 2


def test_influencer_search_by_id(elasticsearch, db_session, multiple_influencers):
    rs = InfluencerSearch().search(multiple_influencers[0].id)
    assert rs.count() == 1
    assert rs.first().id == multiple_influencers[0].id


def test_influencer_search_by_interests(
    elasticsearch,
    db_session,
    influencer_factory,
    instagram_account_factory,
    user_factory,
    db_region,
):
    # Arrange
    interest_a = Interest(name="A")
    interest_b = Interest(name="B")
    influencers = [
        influencer_factory(
            target_region=db_region, interests=[interest_a if i == 0 else interest_b]
        )
        for i in range(2)
    ]
    db_session.add_all(influencers)
    db_session.commit()
    for influencer in influencers:
        update_influencer_info(influencer.id)
    elasticsearch.indices.refresh()

    rs = InfluencerSearch().filter_interests([interest_a.id])
    assert rs.count() == 1
    assert rs.first().id == influencers[0].id

    rs = InfluencerSearch().filter_interests([interest_b.id])
    assert rs.count() == 1
    assert rs.first().id == influencers[1].id


def test_influencer_search_by_age(
    elasticsearch,
    db_session,
    influencer_factory,
    instagram_account_factory,
    user_factory,
    db_region,
):
    # Arrange
    now = dt.datetime.now(dt.timezone.utc)
    influencers = [
        influencer_factory(
            target_region=db_region,
            user=user_factory(birthday=now.replace(year=now.year - (20 + i + 1)).date()),
        )
        for i in range(2)
    ]
    db_session.add_all(influencers)
    db_session.commit()
    for influencer in influencers:
        update_influencer_info(influencer.id)
    elasticsearch.indices.refresh()

    rs = InfluencerSearch().filter_age(min_age=21, max_age=21)
    assert rs.count() == 1
    assert rs.first().id == influencers[0].id

    rs = InfluencerSearch().filter_age(min_age=22, max_age=22)
    assert rs.count() == 1
    assert rs.first().id == influencers[1].id

    rs = InfluencerSearch().filter_age(min_age=21, max_age=22)
    assert rs.count() == 2


def _same_influencers(influencers_a, influencers_b):
    return sorted([i.id for i in influencers_a]) == sorted([i.id for i in influencers_b])


def test_influencer_search_by_followers(
    elasticsearch,
    db_session,
    influencer_factory,
    instagram_account_factory,
    db_region,
    user_factory,
):
    # Arrange
    influencers = [
        influencer_factory(
            instagram_account=instagram_account_factory(
                ig_username=str(i) + "_infl",
                ig_user_id=str(i),
                ig_media_id=str(i),
                token=str(i),
                ig_biography="",
                followers=(i + 1) * 100,
            ),
            state="reviewed",
            target_region=db_region,
            user=user_factory(),
        )
        for i in range(4)
    ]
    db_session.add_all(influencers)
    db_session.commit()
    for influencer in influencers:
        update_influencer_info(influencer.id)
    elasticsearch.indices.refresh()

    # Act and Assert

    # only min
    assert _same_influencers(
        InfluencerSearch().filter_followers(min_followers=200).all(), influencers[1:]
    )
    assert _same_influencers(
        InfluencerSearch().filter_followers(min_followers=300).all(), influencers[2:]
    )
    assert _same_influencers(
        InfluencerSearch().filter_followers(min_followers=400).all(), influencers[3:]
    )

    # only max
    assert _same_influencers(
        InfluencerSearch().filter_followers(max_followers=100).all(), influencers[:1]
    )
    assert _same_influencers(
        InfluencerSearch().filter_followers(max_followers=200).all(), influencers[:2]
    )
    assert _same_influencers(
        InfluencerSearch().filter_followers(max_followers=300).all(), influencers[:3]
    )

    # both
    assert _same_influencers(
        InfluencerSearch().filter_followers(min_followers=100, max_followers=300).all(),
        influencers[:3],
    )
    assert _same_influencers(
        InfluencerSearch().filter_followers(min_followers=200, max_followers=300).all(),
        influencers[1:3],
    )
    assert _same_influencers(
        InfluencerSearch().filter_followers(min_followers=300, max_followers=400).all(),
        influencers[2:4],
    )

    # min higher than max
    assert _same_influencers(
        InfluencerSearch().filter_followers(min_followers=400, max_followers=100).all(), []
    )


def test_influencer_search_by_gender(
    elasticsearch,
    db_session,
    influencer_factory,
    instagram_account_factory,
    db_region,
    user_factory,
):
    alice, bob = (
        influencer_factory(
            instagram_account=instagram_account_factory(
                ig_username=str(i) + "_infl",
                ig_user_id=str(i),
                ig_media_id=str(i),
                token=str(i),
                ig_biography="",
                followers=(i + 1) * 100,
            ),
            target_region=db_region,
            user=user_factory(gender="female" if i == 0 else "male"),
        )
        for i in range(2)
    )
    db_session.add_all([alice, bob])
    db_session.commit()
    for influencer in [alice, bob]:
        update_influencer_info(influencer.id)
    elasticsearch.indices.refresh()
    assert [i.id for i in InfluencerSearch().filter_gender("female").all()] == [alice.id]
    assert [i.id for i in InfluencerSearch().filter_gender("male").all()] == [bob.id]


def test_influencer_search_by_engagements(
    elasticsearch,
    db_session,
    influencer_factory,
    instagram_account_factory,
    db_region,
    user_factory,
):
    influencers = [
        influencer_factory(
            instagram_account=instagram_account_factory(
                ig_username=str(i) + "_infl",
                ig_user_id=str(i),
                ig_media_id=str(i),
                token=str(i),
                ig_biography="",
                engagement=(i + 1) * 0.1,
                followers=1000,
            ),
            target_region=db_region,
        )
        for i in range(4)
    ]
    """
    Engagements are 90, 180, 270, 360 (based on ENGAGEMENT_ESTIMATION_MODIFIER being 0.9)
    """
    db_session.add_all(influencers)
    db_session.commit()
    for influencer in influencers:
        update_influencer_info(influencer.id)
    elasticsearch.indices.refresh()

    assert _same_influencers(
        InfluencerSearch()
        .filter_estimated_engagements_per_post(min_engagements=90, max_engagements=90)
        .all(),
        [influencers[0]],
    )
    assert _same_influencers(
        InfluencerSearch()
        .filter_estimated_engagements_per_post(min_engagements=180, max_engagements=180)
        .all(),
        [influencers[1]],
    )
    assert _same_influencers(
        InfluencerSearch()
        .filter_estimated_engagements_per_post(min_engagements=270, max_engagements=270)
        .all(),
        [influencers[2]],
    )
    assert _same_influencers(
        InfluencerSearch()
        .filter_estimated_engagements_per_post(min_engagements=360, max_engagements=360)
        .all(),
        [influencers[3]],
    )
    assert _same_influencers(
        InfluencerSearch()
        .filter_estimated_engagements_per_post(min_engagements=90, max_engagements=180)
        .all(),
        influencers[0:2],
    )
    assert _same_influencers(
        InfluencerSearch()
        .filter_estimated_engagements_per_post(min_engagements=180, max_engagements=360)
        .all(),
        influencers[1:4],
    )
