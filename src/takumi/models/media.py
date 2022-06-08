from sqlalchemy import DDL, Index, event, func
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import SoftEnum, UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str


class TYPES:
    IMAGE = "image"
    VIDEO = "video"

    @staticmethod
    def values():
        return [TYPES.IMAGE, TYPES.VIDEO]


class OWNER_TYPES:
    INSTAGRAM_POST = "instagram_post"
    STORY_FRAME = "story_frame"
    SUBMISSION = "submission"
    INSIGHT = "insight"
    AUDIENCE_INSIGHT = "audience_insight"
    TIKTOK_POST = "tiktok_post"

    @staticmethod
    def values():
        return [
            OWNER_TYPES.INSTAGRAM_POST,
            OWNER_TYPES.STORY_FRAME,
            OWNER_TYPES.SUBMISSION,
            OWNER_TYPES.INSIGHT,
            OWNER_TYPES.AUDIENCE_INSIGHT,
            OWNER_TYPES.TIKTOK_POST,
        ]


class UnknownMediaTypeException(Exception):
    pass


class Media(db.Model):
    __tablename__ = "media"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())

    type = db.Column(SoftEnum(*TYPES.values()), nullable=False)
    url = db.Column(db.String, nullable=False)

    owner_id = db.Column(UUIDString, nullable=False)
    owner_type = db.Column(SoftEnum(*OWNER_TYPES.values()), nullable=False)

    order = db.Column(db.Integer)

    @staticmethod
    def from_dict(d, owner):
        """Return the correct media based on the type"""
        if d["type"] == "video":
            return Video(
                id=d.get("id", uuid4_str()),
                url=d["url"],
                thumbnail=d.get("thumbnail"),
                order=d.get("order"),
                owner_type=owner.__tablename__,
                owner_id=owner.id,
            )
        elif d["type"] == "image":
            return Image(
                id=d.get("id", uuid4_str()),
                url=d["url"],
                order=d.get("order"),
                owner_type=owner.__tablename__,
                owner_id=owner.id,
            )
        raise UnknownMediaTypeException()

    __table_args__ = (
        Index("ix_media_owner_id", "owner_id"),
        Index("ix_media_owner_type_owner_id", "owner_type", "owner_id"),
    )

    __mapper_args__ = {"polymorphic_identity": "media", "polymorphic_on": type}


# fmt: off
media_triggers = DDL("""
CREATE OR REPLACE FUNCTION get_dynamic_table_record_id(tname TEXT, id UUID) RETURNS SETOF UUID AS $$
BEGIN
    RETURN QUERY EXECUTE 'SELECT id FROM ' || tname || ' WHERE id = ''' || id || '''';
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;

CREATE OR REPLACE FUNCTION honor_owner_fk_constraint() RETURNS trigger AS $$
BEGIN
    IF NEW.owner_id IS NOT NULL
        AND NEW.owner_type IS NOT NULL
        AND (SELECT * FROM get_dynamic_table_record_id(NEW.owner_type, NEW.owner_id)) IS NULL
    THEN
        RAISE EXCEPTION 'exc';  -- rollback
    END IF;
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION delete_related_media() RETURNS trigger AS $$
BEGIN
    DELETE FROM "media" m
    WHERE m.owner_type = TG_ARGV[0]
    AND m.owner_id = OLD.id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_related_media() RETURNS trigger AS $$
BEGIN
    UPDATE "media"
        SET owner_id = NEW.id
        WHERE owner_id = OLD.id
        AND owner_type = TG_ARGV[0];
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER fki_media_owner_id
BEFORE INSERT ON media
FOR EACH ROW EXECUTE PROCEDURE honor_owner_fk_constraint('insert');

CREATE TRIGGER fku_media_owner_id
BEFORE UPDATE ON media
FOR EACH ROW EXECUTE PROCEDURE honor_owner_fk_constraint('update');
""")
# fmt: on
event.listen(Media.__table__, "after_create", media_triggers.execute_if(dialect="postgresql"))  # type: ignore


class Video(Media):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = TYPES.VIDEO

    thumbnail = db.Column(db.String)

    __mapper_args__ = {"polymorphic_identity": "video"}

    def __repr__(self):
        return f"<Video ({self.order}: {self.url})>"


class Image(Media):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = TYPES.IMAGE

    def __repr__(self):
        return f"<Image ({self.order}: {self.url})>"

    __mapper_args__ = {"polymorphic_identity": "image"}
