from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.orm import relationship
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import UUIDString

from takumi.extensions import db

if TYPE_CHECKING:
    from takumi.models import Comment, User  # noqa


class UserCommentAssociation(db.Model):
    __tablename__ = "user_comment_association"

    created = db.Column(UtcDateTime, server_default=func.now(), nullable=False)

    user_id = db.Column(
        "user_id", UUIDString, db.ForeignKey("user.id", ondelete="cascade"), primary_key=True
    )
    user = relationship("User", back_populates="comments_association")
    comment_id = db.Column(
        "comment_id", UUIDString, db.ForeignKey("comment.id", ondelete="cascade"), primary_key=True
    )
    comment = relationship("Comment", back_populates="users_association")

    def __repr__(self):
        return "<UserCommentAssociation: <User: {}> <Comment: {}>>".format(
            self.user_id, self.comment_id
        )

    def create(user, comment):
        association = UserCommentAssociation(user_id=user.id, comment_id=comment.id)
        association.user = user
        comment.users_association.append(association)
        return association
