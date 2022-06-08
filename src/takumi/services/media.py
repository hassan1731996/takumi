from takumi.extensions import db
from takumi.models import Media
from takumi.models.media import OWNER_TYPES
from takumi.services import Service


class MediaService(Service):
    """
    Represents the business model for Media. This isolates the database
    from the application.
    """

    SUBJECT = Media

    @property
    def media(self):
        return self.subject

    @staticmethod
    def get_by_id(id):
        return db.session.query(Media).get(id)

    @staticmethod
    def get_insight_media_by_id(id):
        return (
            db.session.query(Media)
            .filter(Media.owner_type == OWNER_TYPES.INSIGHT, Media.id == id)
            .one_or_none()
        )

    @staticmethod
    def get_instagram_post__media_by_id(id):
        return (
            db.session.query(Media)
            .filter(Media.owner_type == OWNER_TYPES.INSTAGRAM_POST, Media.id == id)
            .one_or_none()
        )

    @staticmethod
    def get_submission_media_by_id(id):
        return (
            db.session.query(Media)
            .filter(Media.owner_type == OWNER_TYPES.SUBMISSION, Media.id == id)
            .one_or_none()
        )

    @staticmethod
    def get_story_frame_media_by_id(id):
        return (
            db.session.query(Media)
            .filter(Media.owner_type == OWNER_TYPES.STORY_FRAME, Media.id == id)
            .one_or_none()
        )
