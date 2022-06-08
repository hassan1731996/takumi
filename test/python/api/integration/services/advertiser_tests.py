from takumi.models import Region
from takumi.services.advertiser import AdvertiserService
from takumi.utils import uuid4_str


def test_advertiser_service_get_by_id(db_advertiser):
    advertiser = AdvertiserService.get_by_id(db_advertiser.id)
    assert advertiser == db_advertiser


def test_advertiser_service_get_by_domain(db_advertiser):
    advertiser = AdvertiserService.get_by_domain(db_advertiser.domain)
    assert advertiser == db_advertiser


def test_advertiser_service_with_domain_exists(db_advertiser):
    res = AdvertiserService.advertiser_with_domain_exists(db_advertiser.domain)
    assert res is True


def test_advertiser_service_create_advertiser(advertiser_user, db_region):
    res = AdvertiserService.create_advertiser(
        advertiser_user, "uniqueref", "picture", "name ", db_region, "ig user", "vat_number", []
    )

    assert res.domain == "uniqueref"
    assert res.profile_picture == "picture"
    assert res.name == "name"
    assert res.primary_region_id == db_region.id
    assert res.vat_number == "vat_number"
    assert res.info == {"instagram": {"user": "ig user"}}


def test_advertiser_service_update_name(db_advertiser):
    assert db_advertiser.name != "new name"

    with AdvertiserService(db_advertiser) as service:
        service.update_name("new name")

    assert db_advertiser.name == "new name"

    with AdvertiserService(db_advertiser) as service:
        service.update_name("new name with space    ")

    assert db_advertiser.name == "new name with space"


def test_advertiser_service_update_profile_picture(db_advertiser):
    assert db_advertiser.profile_picture != "new picture"

    with AdvertiserService(db_advertiser) as service:
        service.update_profile_picture("new picture")

    assert db_advertiser.profile_picture == "new picture"


def test_advertiser_service_update_region(db_session, db_advertiser):
    # Arrange
    region = Region(
        id=uuid4_str(), name="Some Name", locale_code="en_GB", supported=True, hidden=False
    )
    db_session.add(region)
    db_session.commit()

    assert db_advertiser.primary_region_id != region.id

    # Act
    with AdvertiserService(db_advertiser) as service:
        service.update_region(region.id)

    # Assert
    assert db_advertiser.primary_region_id == region.id


def test_advertiser_service_update_influencer_cooldown(db_advertiser):
    with AdvertiserService(db_advertiser) as service:
        service.update_influencer_cooldown(10)

    assert db_advertiser.influencer_cooldown == 10


def test_advertiser_service_update_archived(db_advertiser):
    assert db_advertiser.archived is False

    with AdvertiserService(db_advertiser) as service:
        service.update_archived(True)

    assert db_advertiser.archived is True


def test_advertiser_service_remove_user(db_advertiser, db_advertiser_user):
    assert db_advertiser_user in db_advertiser.users

    with AdvertiserService(db_advertiser) as service:
        service.remove_user(db_advertiser_user)

    assert db_advertiser_user not in db_advertiser.users
