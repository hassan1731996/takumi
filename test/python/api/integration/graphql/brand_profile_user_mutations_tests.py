from takumi.gql.mutation.user import RemoveBrandProfileUser
from takumi.models import User


def test_remove_brand_profile_user_success(
    client, db_advertiser_brand_profile_user, db_developer_user
):
    user = User.query.filter(User.id == db_advertiser_brand_profile_user.id).one_or_none()
    assert user.id == db_advertiser_brand_profile_user.id
    with client.user_request_context(db_developer_user):
        response = RemoveBrandProfileUser().mutate("info", user_id=user.id)
    user = User.query.filter(User.id == db_advertiser_brand_profile_user.id).one_or_none()
    assert user is None
    assert response.ok is True
