import pytest

from takumi.models import Campaign, Region
from takumi.services.exceptions import ServiceException
from takumi.services.targeting import TargetingService
from takumi.utils import uuid4_str


@pytest.fixture(scope="function")
def db_targeting(db_campaign):
    yield db_campaign.targeting


def test_targeting_service_create_targeting(market, db_advertiser):
    campaign = Campaign(
        id=uuid4_str(),
        state="launched",
        advertiser=db_advertiser,
        market_slug=market.slug,
        timezone="America/New_York",
        price=1_000_000,
        list_price=1_000_000,
    )
    targeting = TargetingService.create_targeting(campaign.id, market, db_advertiser)

    assert targeting.campaign_id == campaign.id
    assert targeting.regions == [db_advertiser.primary_region]


def test_targeting_service_update_regions(db_session, db_targeting, market):
    # Arrange
    region = Region(id=uuid4_str(), name="test_name", market_slug=market.slug)
    db_session.add(region)
    db_session.commit()
    assert region not in db_targeting.regions

    # Act
    with TargetingService(db_targeting) as service:
        service.update_regions([region.id])

    # Assert
    assert region in db_targeting.regions


def test_targeting_service_update_gender(db_targeting):
    # Arrange
    assert db_targeting.gender is None

    # Act
    with TargetingService(db_targeting) as service:
        service.update_gender("male")

    # Assert
    assert db_targeting.gender == "male"


def test_targeting_service_update_ages(db_targeting):
    # Arrange
    ages = [10, 21, 43, 45]
    assert db_targeting.ages is None

    # Act
    with TargetingService(db_targeting) as service:
        service.update_ages(ages)

    # Assert
    assert db_targeting.ages == sorted(ages)


def test_targeting_service_update_interests(db_targeting):
    # Arrange
    interests = [uuid4_str(), uuid4_str()]
    assert db_targeting.interest_ids != interests

    # Act
    with TargetingService(db_targeting) as service:
        service.update_interests(interests)

    # Assert
    assert db_targeting.interest_ids == interests


def test_targeting_service_update_followers_raises_if_max_below_campaign_min(
    db_targeting, db_campaign
):
    assert db_targeting.max_followers is None
    assert db_targeting.min_followers is None

    with pytest.raises(ServiceException, match=r"Maximum followers can't be below 1000"):
        TargetingService(db_targeting).update_followers(min_followers=None, max_followers=999)

    assert db_targeting.max_followers is None

    with TargetingService(db_targeting) as service:
        service.update_followers(min_followers=None, max_followers=1000)

    assert db_targeting.max_followers == 1000

    with TargetingService(db_targeting) as service:
        service.update_followers(min_followers=None, max_followers=1001)

    assert db_targeting.max_followers == 1001


def test_targeting_service_update_followers_raises_if_min_below_campaign_min(
    db_targeting, db_campaign
):
    assert db_targeting.max_followers is None
    assert db_targeting.min_followers is None

    with pytest.raises(ServiceException, match=r"Minimum followers can't be below 1000"):
        TargetingService(db_targeting).update_followers(min_followers=999, max_followers=None)

    assert db_targeting.min_followers is None

    with TargetingService(db_targeting) as service:
        service.update_followers(min_followers=1000, max_followers=None)

    assert db_targeting.min_followers == 1000

    with TargetingService(db_targeting) as service:
        service.update_followers(min_followers=1001, max_followers=None)

    assert db_targeting.min_followers == 1001


def test_targeting_service_update_followers_range_outside_old_range(db_targeting, db_campaign):
    with TargetingService(db_targeting) as service:
        service.update_followers(min_followers=30_000, max_followers=50_000)

    with TargetingService(db_targeting) as service:
        service.update_followers(min_followers=20_000, max_followers=20_000)


def test_targeting_service_update_followers_clearing_values(db_targeting, db_campaign):
    with TargetingService(db_targeting) as service:
        service.update_followers(min_followers=30_000, max_followers=50_000)

    assert db_targeting.min_followers == 30_000
    assert db_targeting.max_followers == 50_000

    with TargetingService(db_targeting) as service:
        service.update_followers(min_followers=None, max_followers=50_000)

    assert db_targeting.min_followers == None
    assert db_targeting.max_followers == 50_000

    with TargetingService(db_targeting) as service:
        service.update_followers(min_followers=None, max_followers=100_000)

    assert db_targeting.min_followers == None
    assert db_targeting.max_followers == 100_000

    with TargetingService(db_targeting) as service:
        service.update_followers(min_followers=150_000, max_followers=None)
