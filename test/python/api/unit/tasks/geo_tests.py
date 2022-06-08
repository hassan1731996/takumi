from takumi.tasks.geo import update_influencer_location_with_pickpoint


def test_update_influencer_location_with_pickpoint_sets_current_region_only_if_accurate_location_set_before(
    monkeypatch, influencer, region
):
    # Arrange
    influencer.current_region_id = None
    influencer.target_region_id = None
    influencer.info["accurate_location_set"] = True

    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: influencer)
    monkeypatch.setattr("takumi.tasks.geo.query_pickpoint", lambda *args: dict(address="some"))
    monkeypatch.setattr("takumi.tasks.geo.region_from_osm_address", lambda *args: region)
    monkeypatch.setattr("takumi.tasks.geo.db.session.commit", lambda *args: None)

    # Act
    update_influencer_location_with_pickpoint(influencer.id, "10.0", "20.0")

    # Assert
    assert influencer.current_region_id == region.id
    assert influencer.target_region_id is None


def test_update_influencer_location_with_pickpoint_sets_current_and_target_region(
    monkeypatch, influencer, region
):
    # Arrange
    influencer.current_region_id = None
    influencer.target_region_id = None
    influencer.info["accurate_location_set"] = False

    monkeypatch.setattr("flask_sqlalchemy.BaseQuery.get", lambda *args: influencer)
    monkeypatch.setattr("takumi.tasks.geo.query_pickpoint", lambda *args: dict(address="some"))
    monkeypatch.setattr("takumi.tasks.geo.region_from_osm_address", lambda *args: region)
    monkeypatch.setattr("takumi.tasks.geo.db.session.commit", lambda *args: None)

    # Act
    update_influencer_location_with_pickpoint(influencer.id, "10.0", "20.0")

    # Assert
    assert influencer.current_region_id == region.id
    assert influencer.target_region_id == region.id
