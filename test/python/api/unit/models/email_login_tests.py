from unittest import TestCase

from takumi.models import EmailLogin
from takumi.utils import uuid4_str


class TestEmailLoginModel(TestCase):
    def setUp(self) -> None:
        self.email_login_verified = EmailLogin(user_id=uuid4_str(), verified=True)
        self.email_login_unverified_invitation_not_sent = EmailLogin(
            user_id=uuid4_str(), verified=False, invitation_sent=False
        )
        self.email_login_unverified_invitation_sent = EmailLogin(
            user_id=uuid4_str(), verified=False, invitation_sent=True
        )

    def test_verified_email_value_invitation_sent(self):
        self.assertTrue(self.email_login_verified.has_invitation_sent)

    def test_unverified_email_invitation_not_sent(self):
        self.assertFalse(self.email_login_unverified_invitation_not_sent.has_invitation_sent)

    def test_unverified_email_invitation_sent(self):
        self.assertTrue(self.email_login_unverified_invitation_sent.has_invitation_sent)
