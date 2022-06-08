import mock

from takumi.models import Region
from takumi.utils.region import get_subregion_from_coords

# _A_A is a subregion within _A and so on
POLYGON_A = [[1.0, 1.0], [10.0, 1.0], [10.0, 10.0], [1.0, 10.0]]
POLYGON_A_A = [[2.0, 2.0], [9.0, 2.0], [9.0, 9.0], [2.0, 9.0]]
POLYGON_A_A_A = [[3.0, 3.0], [8.0, 3.0], [8.0, 8.0], [3.0, 8.0]]
POLYGON_B = [[101.0, 101.0], [110.0, 101.0], [110.0, 110.0], [101.0, 110.0]]


POINT_IN_A = {"lat": 1.5, "lon": 1.5}
POINT_IN_A_A = {"lat": 2.5, "lon": 2.5}
POINT_IN_A_A_A = {"lat": 3.5, "lon": 3.5}
POINT_IN_B = {"lat": 104.0, "lon": 104.0}
POINT_OUTSIDE = {"lat": -1.0, "lon": -1.0}


def test_get_subregion_from_coords_subregion_found(client):
    level1 = Region(id=1, name="level1", polygons=[POLYGON_A])
    level2 = Region(id=2, name="level2", polygons=[POLYGON_A_A], path=[level1])
    level3 = Region(id=3, name="level3", polygons=[POLYGON_A_A_A], path=[level1, level2])

    with mock.patch("sqlalchemy.orm.Query.all") as mock_all:
        mock_all.side_effect = [
            [level1],
            [level2, level3],
        ]  # First return a list of all top then sub regions

        region = get_subregion_from_coords(**POINT_IN_A_A)  # Within A and A_A

    assert region == level2


def test_get_subregion_from_coords_only_topregion_found(client):
    top_region = Region(id=1, name="top", polygons=[POLYGON_A])
    sub_region = Region(id=2, name="sub", polygons=[POLYGON_A_A])
    with mock.patch("sqlalchemy.orm.Query.all") as mock_all:
        mock_all.side_effect = [
            [top_region],
            [sub_region],
        ]  # First return a list of all top then sub regions

        region = get_subregion_from_coords(**POINT_IN_A)  # Within A, but not A_A

    assert region is None


def test_get_subregion_from_coords_returns_lowest_level_region_found(client):
    level1 = Region(id=1, name="level1", polygons=[POLYGON_A])
    level2 = Region(id=2, name="level2", polygons=[POLYGON_A_A], path=[level1])
    level3 = Region(id=3, name="level3", polygons=[POLYGON_A_A_A], path=[level1, level2])

    with mock.patch("sqlalchemy.orm.Query.all") as mock_all:
        mock_all.side_effect = [
            [level1],
            [level2, level3],
        ]  # First top level region, then the ones below it
        region = get_subregion_from_coords(**POINT_IN_A_A_A)
    assert region is level3

    with mock.patch("sqlalchemy.orm.Query.all") as mock_all:
        mock_all.side_effect = [[level1], [level3, level2]]  # Reverse the order
        region = get_subregion_from_coords(**POINT_IN_A_A_A)
    assert region is level3


def test_get_subregion_from_coords_topregion_found_with_no_subregion(client):
    top_region = Region(id=1, name="top", polygons=[POLYGON_B])
    with mock.patch("sqlalchemy.orm.Query.all") as mock_all:
        mock_all.side_effect = [[top_region], []]  # First return a list of all top then sub regions

        region = get_subregion_from_coords(**POINT_IN_B)  # Within A, but not A_A

    assert region is None


def test_get_subregion_no_top_region_found(client):
    with mock.patch("sqlalchemy.orm.Query.all") as mock_all:
        mock_all.side_effect = [[], []]  # First return a list of all top then sub regions

        region = get_subregion_from_coords(**POINT_OUTSIDE)  # Outside of all polygons

    assert region is None
