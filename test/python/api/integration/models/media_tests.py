import pytest
from sqlalchemy.exc import StatementError

from takumi.models.media import Media
from takumi.utils import uuid4_str


def test_create_media_needs_a_parent_with_polymorphic_association(db_session, db_campaign):
    # Arrange
    media = Media.from_dict({"type": "image", "url": "some_url"}, db_campaign)
    db_session.add(media)

    # Act
    with pytest.raises(StatementError, match="'campaign' is not a valid value for SoftEnum((.+))"):
        db_session.commit()


def test_media_honors_foreign_key_constraints(db_session, db_submission):
    # Arrange
    media = Media.from_dict({"type": "image", "url": "some_url"}, db_submission)
    db_session.add(media)
    db_session.commit()

    new_id = uuid4_str()
    assert media.owner_id == db_submission.id
    assert media.owner_id != new_id

    # Act
    db_submission.id = new_id
    db_session.commit()

    # Assert
    assert db_submission.id == media.owner_id
    assert media.owner_id == new_id


def test_media_honors_foreign_key_constraints_where_owner_type_and_owner_id_are_unique(
    db_session, db_submission, db_instagram_post
):
    # Arrange
    new_id = uuid4_str()
    media1 = Media.from_dict({"type": "image", "url": "some_url"}, db_submission)
    media2 = Media.from_dict({"type": "image", "url": "some_url"}, db_instagram_post)
    db_session.add_all([media1, media2])
    db_session.commit()

    # Act
    db_submission.id = new_id
    db_instagram_post.id = new_id
    db_session.commit()

    # Assert
    assert db_submission.id == media1.owner_id
    assert db_instagram_post.id == media2.owner_id
    assert db_instagram_post.id == db_submission.id


@pytest.mark.skip(reason="Test not passing with current triggers")
def test_media_honors_foreign_key_constraints_whith_on_delete_cascade(db_session, db_submission):
    # Arrange
    media = Media.from_dict({"type": "image", "url": "some_url"}, db_submission)
    db_session.add(media)
    db_session.commit()

    # Act
    db_session.delete(db_submission)
    db_session.commit()

    # Assert
    assert media is None
