import datetime as dt

from core.common.utils import DictObject

from takumi.gql.mutation.influencer_information import SetInfluencerInformation
from takumi.models.influencer_information import EyeColour, HairColour, HairType, Tag

mock_info = DictObject(context={})
mock_info.context.get = lambda *_: None


def test_influencer_update_information_updates_values(
    client, db_influencer, influencer_user, db_session
):
    hair_colour_id = HairColour.all()[0].id
    hair_type_id = HairType.all()[0].id
    eye_colour_id = EyeColour.all()[0].id

    tag1 = Tag.all()[0]
    tag2 = Tag.all()[1]

    tag_ids = [tag1.id, tag2.id]

    today = dt.datetime.now(dt.timezone.utc).date()

    with client.user_request_context(influencer_user):
        SetInfluencerInformation.mutate(
            "root",
            mock_info,
            db_influencer.username,
            appearance={
                "hair_colour": hair_colour_id,
                "hair_type": hair_type_id,
                "eye_colour": eye_colour_id,
                "glasses": True,
            },
            account_type="business",
            languages=["en"],
            tags=tag_ids,
            children=[dict(gender="male", birthday=today)],
        )

    assert db_influencer.information is not None

    assert db_influencer.information.hair_colour.id == hair_colour_id
    assert db_influencer.information.hair_type.id == hair_type_id
    assert db_influencer.information.eye_colour.id == eye_colour_id
    assert db_influencer.information.glasses == True

    assert db_influencer.information.account_type == "business"

    assert db_influencer.information.tag_ids == [tag1.id, tag2.id]

    assert len(db_influencer.information.children) == 1
    assert db_influencer.information.children[0].gender == "male"
    assert db_influencer.information.children[0].birthday == today


def test_influencer_update_information_removing_children_removes_children(
    client, db_influencer, influencer_user, db_session
):
    today = dt.datetime.now(dt.timezone.utc).date()

    with client.user_request_context(influencer_user):
        SetInfluencerInformation.mutate(
            "root",
            mock_info,
            db_influencer.username,
            children=[dict(gender="male", birthday=today)],
        )

    assert len(db_influencer.information.children) == 1

    with client.user_request_context(influencer_user):
        SetInfluencerInformation.mutate("root", mock_info, db_influencer.username, children=[])

    assert len(db_influencer.information.children) == 0


def test_influencer_update_information_changing_childs_gender_changes_its_gender(
    client, db_influencer, influencer_user, db_session
):
    today = dt.datetime.now(dt.timezone.utc).date()

    with client.user_request_context(influencer_user):
        SetInfluencerInformation.mutate(
            "root",
            mock_info,
            db_influencer.username,
            children=[dict(gender="male", birthday=today)],
        )

    assert len(db_influencer.information.children) == 1

    child = db_influencer.information.children[0]

    with client.user_request_context(influencer_user):
        SetInfluencerInformation.mutate(
            "root", mock_info, db_influencer.username, children=[dict(id=child.id, gender="female")]
        )

    child = db_influencer.information.children[0]
    assert child.gender == "female"


def test_influencer_update_information_removing_tags_removes_tags(
    client, db_influencer, influencer_user, db_session
):
    tag1 = Tag.all()[0]
    tag2 = Tag.all()[1]

    tag_ids = [tag1.id, tag2.id]

    with client.user_request_context(influencer_user):
        SetInfluencerInformation.mutate("root", mock_info, db_influencer.username, tags=tag_ids)

    assert db_influencer.information.tag_ids == [tag1.id, tag2.id]

    with client.user_request_context(influencer_user):
        SetInfluencerInformation.mutate("root", mock_info, db_influencer.username, tags=[])

    assert db_influencer.information.tags == []
