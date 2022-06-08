import datetime as dt
import os

from sqlalchemy import func
from sqlalchemy.orm import backref, relationship
from sqlalchemy_utc import UtcDateTime
from werkzeug.security import check_password_hash, generate_password_hash

from core.common.sqla import SimpleTSVectorType, UUIDString

from takumi.constants import EMAIL_VERIFICATION_MAX_AGE_SECONDS, PASSWORD_HASH_METHOD
from takumi.extensions import db

from .user import User


class EmailLogin(db.Model):
    __tablename__ = "email_login"

    email = db.Column(db.String, primary_key=True)
    created = db.Column(UtcDateTime, server_default=func.now())
    modified = db.Column(UtcDateTime, onupdate=func.now())
    password_hash = db.Column(db.String)
    verified = db.Column(db.Boolean, server_default="f", nullable=False)
    invitation_sent = db.Column(db.Boolean, server_default="t", nullable=False)

    user_id = db.Column(
        UUIDString, db.ForeignKey(User.id, ondelete="cascade"), nullable=False, index=True
    )
    user = relationship(User, backref=backref("email_login", uselist=False, lazy="joined"))
    otp_salt = db.Column(db.String(length=64))

    search_vector = db.Column(SimpleTSVectorType("email", remove_symbols=""), index=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method=PASSWORD_HASH_METHOD)

    def check_password(self, password):
        return self.password_hash is not None and check_password_hash(self.password_hash, password)

    def reset_otp(self):
        """Resetting the `otp_salt` for all OTP requests accomplishes
        a) 'windowing' so only the most recent OTP is valid and
        b) a `salt` argument for `itsdangerous`.
        """
        self.otp_salt = os.urandom(32).hex()

    # Respecting case sensitivity in emails to comply with RFC 5321
    @classmethod
    def get(cls, email):
        return cls.query.filter(func.lower(cls.email) == func.lower(email)).one_or_none()

    @classmethod
    def get_or_create(cls, email):
        email_login = cls.query.filter(func.lower(cls.email) == func.lower(email)).one_or_none()
        if email_login:
            return email_login
        return cls(email=email.lower())

    @classmethod
    def create(cls, email, user, password=None):
        email_login = cls(email=email.lower(), user=user)
        if password is not None:
            email_login.set_password(password)
        return email_login

    @property
    def time_to_live(self):
        if not self.verified:
            expiration_date = self.created + dt.timedelta(
                seconds=EMAIL_VERIFICATION_MAX_AGE_SECONDS
            )
            return (expiration_date - dt.datetime.now(dt.timezone.utc)).total_seconds()

    @property
    def has_invitation_sent(self):
        if self.verified:
            return True
        return self.invitation_sent

    def __repr__(self):
        return f"<EmailLogin: {self.email}>"
