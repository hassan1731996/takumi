from takumi.models import Region
from takumi.services.region import RegionService
from takumi.utils import uuid4_str


def test_region_service_get_by_id(db_region):
    region = RegionService.get_by_id(db_region.id)
    assert region == db_region


def test_region_service_get_all_by_ids(db_session, db_region, market):
    # Arrange
    db_region2 = Region(id=uuid4_str(), name="test_name", market_slug=market.slug)
    db_session.add(db_region2)
    db_session.commit()

    # Act
    regions = RegionService.get_all_by_ids([db_region.id, db_region2.id])

    # Assert
    assert regions == [db_region, db_region2]
