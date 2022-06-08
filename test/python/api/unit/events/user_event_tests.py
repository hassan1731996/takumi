from takumi.events.user import UserLog


def test_set_user_device_sets_device(app, influencer_user, device):
    # Arrange
    log = UserLog(influencer_user)

    # Act
    log.add_event("set_device", {"device_id": device.id})

    # Assert
    assert influencer_user.device_id == device.id
