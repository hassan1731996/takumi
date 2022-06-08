from unittest import mock

from takumi.gql.query import UserQuery
from takumi.roles import permissions


def test_get_brand_profile_user_by_advertiser_success(db_advertiser_brand_profile_user):
    advertiser_id = db_advertiser_brand_profile_user.advertisers[0].id
    with mock.patch.object(permissions, "access_all_advertisers", mock.Mock(can=lambda: True)):
        response = UserQuery().resolve_brand_profile_user_for_advertiser("info", advertiser_id)
    assert response.id == db_advertiser_brand_profile_user.id


def test_get_brand_profile_user_by_advertiser_failed_no_perm(db_advertiser_brand_profile_user):
    advertiser_id = db_advertiser_brand_profile_user.advertisers[0].id
    with mock.patch.object(permissions, "access_all_advertisers", mock.Mock(can=lambda: False)):
        response = UserQuery().resolve_brand_profile_user_for_advertiser("info", advertiser_id)
    assert response is None


def test_get_brand_profile_user_by_advertiser_user_not_exist(db_advertiser_user):
    advertiser_id = db_advertiser_user.advertisers[0].id
    with mock.patch.object(permissions, "access_all_advertisers", mock.Mock(can=lambda: True)):
        response = UserQuery().resolve_brand_profile_user_for_advertiser("info", advertiser_id)
    assert response is None
