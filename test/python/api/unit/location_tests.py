import mock

from takumi.location import (
    update_influencer_location_by_ip,
    update_influencer_location_with_coordinates,
)
from takumi.models import Region


def test_update_influencer_location_by_ip_doesnt_set_location_if_accurate_location_sent(influencer):
    influencer.info["accurate_location_set"] = True
    with mock.patch("takumi.location.InfluencerLog") as mock_log:
        update_influencer_location_by_ip(influencer)

    mock_log.assert_not_called()


def test_update_influencer_location_by_ip_does_set_target_region_if_not_set(
    influencer, region, monkeypatch
):
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr("takumi.location.GeoRequest.country_code", lambda self: "IS")

    influencer.info["accurate_location_set"] = False
    influencer.target_region = None
    influencer.current_region = None

    with mock.patch("takumi.location.InfluencerLog") as mock_log:
        with mock.patch("takumi.location.Region") as mock_region:
            mock_region.get_by_locale.return_value = region
            update_influencer_location_by_ip(influencer)

    mock_log.assert_called_with(influencer)
    mock_add_event = mock_log.return_value.add_event
    assert mock_add_event.call_count == 2
    mock_add_event.assert_has_calls(
        [
            mock.call("set_target_region", {"source": "ip", "region_id": region.id}),
            mock.call("set_current_region", {"source": "ip", "region_id": region.id}),
        ]
    )


def test_update_influencer_location_by_ip_does_not_set_target_region_if_already_set(
    influencer, region, monkeypatch
):
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr("takumi.location.GeoRequest.country_code", lambda self: "IS")

    influencer.info["accurate_location_set"] = False
    influencer.target_region = Region()
    influencer.current_region = Region()

    with mock.patch("takumi.location.InfluencerLog") as mock_log:
        with mock.patch("takumi.location.Region") as mock_region:
            mock_region.get_by_locale.return_value = region
            update_influencer_location_by_ip(influencer)

    mock_log.assert_called_with(influencer)
    mock_add_event = mock_log.return_value.add_event
    mock_add_event.assert_called_once_with(
        "set_current_region", {"source": "ip", "region_id": region.id}
    )


def test_update_influencer_location_by_ip_creates_and_sets_country_as_region_if_exists(
    influencer, monkeypatch
):
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr("takumi.location.GeoRequest.country_code", lambda self: "IS")

    influencer.info["accurate_location_set"] = False
    influencer.target_region = None
    influencer.current_region = None

    with mock.patch("takumi.location.InfluencerLog") as mock_log:
        with mock.patch("takumi.location.Region") as mock_region:
            mock_region.get_by_locale.return_value = None

            update_influencer_location_by_ip(influencer)

    mock_log.assert_called_with(influencer)
    mock_add_event = mock_log.return_value.add_event
    assert mock_add_event.call_count == 2
    mock_add_event.assert_has_calls(
        [
            mock.call(
                "set_target_region", {"source": "ip", "region_id": mock_region.return_value.id}
            ),
            mock.call(
                "set_current_region", {"source": "ip", "region_id": mock_region.return_value.id}
            ),
        ]
    )


def test_update_influencer_location_with_coordinates_sets_subregion_if_exists(
    influencer, region, monkeypatch
):
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)

    with mock.patch("takumi.location.get_subregion_from_coords", return_value=region):
        with mock.patch("takumi.location.InfluencerLog") as mock_log:
            update_influencer_location_with_coordinates(influencer, lat=1, lon=2)

    mock_log.assert_called_with(influencer)
    mock_add_event = mock_log.return_value.add_event
    assert mock_add_event.call_count == 2
    mock_add_event.assert_has_calls(
        [
            mock.call("set_target_region", {"source": "gps", "region_id": region.id}),
            mock.call("set_current_region", {"source": "gps", "region_id": region.id}),
        ]
    )

    assert influencer.info["lat"] == 1
    assert influencer.info["lon"] == 2


def test_update_influencer_location_with_coordinates_initiates_lambda_location_task_if_no_subregion(
    influencer, monkeypatch
):
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    monkeypatch.setattr("takumi.location.get_subregion_from_coords", lambda *args: None)

    with mock.patch("takumi.location.InfluencerLog") as mock_log:
        with mock.patch(
            "takumi.tasks.geo.update_influencer_location_with_pickpoint.delay"
        ) as mock_task:
            update_influencer_location_with_coordinates(influencer, lat=3, lon=4)

    mock_log.assert_not_called()
    mock_task.assert_called()

    assert influencer.info["lat"] == 3
    assert influencer.info["lon"] == 4


def test_update_influencer_location_with_coordinats_doesnt_set_target_region_if_accurate_already(
    influencer, region, monkeypatch
):
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)

    influencer.info["accurate_location_set"] = True

    with mock.patch("takumi.location.get_subregion_from_coords", return_value=region):
        with mock.patch("takumi.location.InfluencerLog") as mock_log:
            update_influencer_location_with_coordinates(influencer, lat=1, lon=2)

    mock_log.assert_called_with(influencer)
    mock_add_event = mock_log.return_value.add_event
    mock_add_event.assert_called_once_with(
        "set_current_region", {"source": "gps", "region_id": region.id}
    )


def test_update_influencer_location_with_coordinats_sets_target_region_to_parent_if_region_unsupported(
    influencer, region_city, region_state, monkeypatch
):
    # Arrange
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    region_city.supported = False

    # Act
    with mock.patch("takumi.location.get_subregion_from_coords", return_value=region_city):
        with mock.patch(
            "takumi.models.region.Region.parent",
            new_callable=mock.PropertyMock,
            return_value=region_state,
        ):
            with mock.patch("takumi.location.InfluencerLog") as mock_log:
                update_influencer_location_with_coordinates(influencer, lat=1, lon=2)

    # Assert
    mock_log.assert_called_with(influencer)
    mock_add_event = mock_log.return_value.add_event
    assert mock_add_event.call_count == 2
    mock_add_event.assert_has_calls(
        [
            mock.call("set_target_region", {"source": "gps", "region_id": region_state.id}),
            mock.call("set_current_region", {"source": "gps", "region_id": region_city.id}),
        ]
    )


def test_update_influencer_location_with_coordinats_sets_target_region_if_region_and_parent_region_are_unsupported(
    influencer, region_city, region_state, monkeypatch
):
    # Arrange
    monkeypatch.setattr("takumi.extensions.db.session.commit", lambda: None)
    region_city.supported = False
    region_state.supported = False

    # Act
    with mock.patch("takumi.location.get_subregion_from_coords", return_value=region_city):
        with mock.patch(
            "takumi.models.region.Region.supported_ancestor",
            new_callable=mock.PropertyMock,
            return_value=None,
        ):
            with mock.patch("takumi.location.InfluencerLog") as mock_log:
                update_influencer_location_with_coordinates(influencer, lat=1, lon=2)

    # Assert
    mock_log.assert_called_with(influencer)
    mock_add_event = mock_log.return_value.add_event
    assert mock_add_event.call_count == 2
    mock_add_event.assert_has_calls(
        [
            mock.call("set_target_region", {"source": "gps", "region_id": region_city.id}),
            mock.call("set_current_region", {"source": "gps", "region_id": region_city.id}),
        ]
    )
