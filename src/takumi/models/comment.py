from typing import TYPE_CHECKING

from sqlalchemy import DDL, Index, event, func
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import SoftEnum, UUIDString

from takumi.extensions import db
from takumi.utils import uuid4_str

from .user_comment_association import UserCommentAssociation

if TYPE_CHECKING:
    from takumi.models import User  # noqa


class OWNER_TYPES:
    OFFER = "offer"

    @staticmethod
    def values():
        return [OWNER_TYPES.OFFER]


class Comment(db.Model):
    __tablename__ = "comment"

    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    created = db.Column(UtcDateTime, server_default=func.now(), nullable=False)
    modified = db.Column(UtcDateTime, onupdate=func.now())

    content = db.Column(db.String, nullable=False)

    creator_id = db.Column(UUIDString, db.ForeignKey("user.id", ondelete="cascade"), nullable=False)
    creator = relationship("User", backref=backref("comments"), uselist=False)

    owner_id = db.Column(UUIDString, nullable=False)
    owner_type = db.Column(SoftEnum(*OWNER_TYPES.values()), nullable=False)

    users_association = relationship("UserCommentAssociation", back_populates="comment")

    __table_args__ = (
        Index("ix_comment_owner_id", "owner_id"),
        Index("ix_comment_owner_type_owner_id", "owner_type", "owner_id"),
    )

    @property
    def seen_by(self):
        return [association.user for association in self.users_association]

    def seen_by_user(self, user_id):
        from takumi.models import UserCommentAssociation

        return (
            UserCommentAssociation.query.filter_by(comment_id=self.id, user_id=user_id).count() > 0
        )

    @staticmethod
    def create(content, creator, owner):
        comment = Comment(
            id=uuid4_str(),
            content=content,
            creator=creator,
            owner_type=owner.__tablename__,
            owner_id=owner.id,
        )
        UserCommentAssociation.create(creator, comment)
        return comment


# fmt: off
comment_triggers = DDL("""
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

CREATE OR REPLACE FUNCTION delete_related_comment() RETURNS trigger AS $$
BEGIN
    DELETE FROM "comment" c
    WHERE c.owner_type = TG_ARGV[0]
    AND c.owner_id = OLD.id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_related_comment() RETURNS trigger AS $$
BEGIN
    UPDATE "comment"
        SET owner_id = NEW.id
        WHERE owner_id = OLD.id
        AND owner_type = TG_ARGV[0];
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER fki_comment_owner_id
BEFORE INSERT ON comment
FOR EACH ROW EXECUTE PROCEDURE honor_owner_fk_constraint('insert');

CREATE TRIGGER fku_comment_owner_id
BEFORE UPDATE ON comment
FOR EACH ROW EXECUTE PROCEDURE honor_owner_fk_constraint('update');
""")
# fmt: on
event.listen(Comment.__table__, "after_create", comment_triggers.execute_if(dialect="postgresql"))  # type: ignore
