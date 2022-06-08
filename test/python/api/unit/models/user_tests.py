# encoding=utf-8

from unittest import TestCase

from takumi.models import Influencer, InstagramAccount, User
from takumi.utils import uuid4_str


class UserTests(TestCase):
    def setUp(self):
        self.user = User(id=uuid4_str())

    def test_user_has_instagram_account_returns_false_if_user_has_no_influencer(self):
        assert self.user.influencer is None
        assert self.user.has_instagram_account is False

    def test_user_has_instagram_account_returns_false_if_user_influencer_has_no_instagram_account(
        self,
    ):
        self.user.influencer = Influencer(id=uuid4_str())
        assert self.user.has_instagram_account is False

    def test_user_has_instagram_account_returns_true_if_user_influencer_has_instagram_account(self):
        instagram_account = InstagramAccount(id=uuid4_str())
        influencer = Influencer(id=uuid4_str(), instagram_account=instagram_account)
        self.user.influencer = influencer

        assert self.user.has_instagram_account is True
