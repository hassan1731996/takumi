import mock
from flask import url_for

from takumi.models import Device, User
from takumi.utils import uuid4_str

test_device_post_data = {
    "id": "4970ea63-fc0c-4b14-9594-a805f17d5468",
    "token": "expo[eca7108b4e3e43e9cc9ebda8d0b30038c2bc2aa3e77e58986beb8921d9cf3f89]",
    "model": "iStone 7.0",
    "os_version": "13.37.0",
    "build_version": "0.6.0 (30)",
    "locale": "en-IS",
}


def _create_device(db_session, **kwargs):
    device_data = dict(
        id=test_device_post_data["id"],
        device_token=test_device_post_data["token"],
        device_model=test_device_post_data["model"],
        os_version=test_device_post_data["os_version"],
    )

    device_data.update(kwargs)
    device = Device(**device_data)
    db_session.add(device)
    db_session.commit()
    return device


def test_post_device_inserts_new_device(db_session, db_influencer, client):
    db_influencer.user.device = None
    with client.use(db_influencer.user):
        with mock.patch("takumi.search.influencer.indexing.update_influencer_info") as mock_update:
            response = client.post(url_for("api.create_device"), data=test_device_post_data)
    assert response.status_code == 201
    assert mock_update.delay.called

    device = db_session.query(Device).first()
    assert db_influencer.device_id == device.id


def test_post_device_deletes_older_install_from_other_user_on_same_device(
    influencer_client, db_session, db_influencer_user, db_influencer
):
    other_user = User(
        id=uuid4_str(), full_name="Other test user", profile_picture="", role_name="influencer"
    )
    db_session.add(other_user)

    # create a new device belonging to other_user
    new_device = _create_device(db_session)
    other_user.device = new_device
    other_user.device.device_token = "TOKEN"

    # now let's create the same device through the API using db_influencer_user
    device_data = test_device_post_data.copy()
    device_data["token"] = other_user.device.device_token
    response = influencer_client.post(url_for("api.create_device"), data=device_data)
    assert response.status_code == 201

    # now device should belong to `db_influencer_user` and not `other_user`
    device = Device.query.get(new_device.id)
    assert device.device_token is None

    assert db_influencer_user.device.id != new_device.id
    assert db_influencer_user.device.device_token == "TOKEN"


def test_post_device_finds_device_by_token(
    influencer_client, db_session, db_influencer_user, db_influencer
):
    test_data = test_device_post_data

    response = influencer_client.post(url_for("api.create_device"), data=test_device_post_data)
    assert response.status_code == 201

    test_data["id"] = uuid4_str()
    response = influencer_client.post(url_for("api.create_device"), data=test_data)
    assert response.status_code == 200
