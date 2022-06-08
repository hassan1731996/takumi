import mock
import pytest

from takumi.error_codes import OUTDATED_CLIENT_VERSION
from takumi.exceptions import ClientUpgradeRequired


class Request:
    def __init__(self, headers):
        self.headers = headers


@mock.patch("takumi.exceptions.get_request_version")
def test_raise_for_version_raises_if_min_version_greater_than_current_version(get_request_version):
    get_request_version.return_value = (1, 0, 0)
    with pytest.raises(ClientUpgradeRequired) as exc:
        ClientUpgradeRequired.raise_for_version((1, 0, 1), Request({}))
    assert exc.value.payload["required_version"] == "1.0.1"
    with pytest.raises(ClientUpgradeRequired) as exc:
        ClientUpgradeRequired.raise_for_version("1.2.3", Request({}))
    assert exc.value.payload["required_version"] == "1.2.3"


@mock.patch("takumi.exceptions.get_request_version")
def test_raise_for_version_does_not_raise_if_min_version_lower_than_current_version(
    get_request_version,
):
    get_request_version.return_value = (3, 1, 5)
    ClientUpgradeRequired.raise_for_version((1, 0, 1), Request({}))
    ClientUpgradeRequired.raise_for_version("1.2.3", Request({}))


def test_raise_for_version_includes_upgrade_url_per_platform():
    ios_upgrade_url = "https://itunes.apple.com/us/app/takumi-connect-with-brands/id1042708237?ls=1"
    android_upgrade_url = "https://play.google.com/store/apps/details?id=com.takumi&hl=en"
    request = Request({"Takumi-Platform-Name": "iPhone OS", "Takumi-Client-Version": "1.2.3"})
    with pytest.raises(ClientUpgradeRequired) as exc:
        ClientUpgradeRequired.raise_for_version((3, 1, 0), request)
    assert exc.value.payload["upgrade_url"] == ios_upgrade_url

    request = Request({"Takumi-Platform-Name": "Android", "Takumi-Client-Version": "1.2.3"})
    with pytest.raises(ClientUpgradeRequired) as exc:
        ClientUpgradeRequired.raise_for_version((3, 1, 0), request)
    assert exc.value.payload["upgrade_url"] == android_upgrade_url


def test_raise_for_version_includes_no_upgrade_url_for_unknown_platform():
    request = Request(
        {"Takumi-Platform-Name": "Windows Mobile OS", "Takumi-Client-Version": "1.2.3"}
    )
    with pytest.raises(ClientUpgradeRequired) as exc:
        ClientUpgradeRequired.raise_for_version((3, 1, 0), request)
    assert "upgrade_url" not in exc.value.payload


def test_raise_for_version_sets_fallback_error_message_store_string_according_to_platform():
    request = Request({"Takumi-Platform-Name": "iPhone OS", "Takumi-Client-Version": "1.2.3"})
    with pytest.raises(ClientUpgradeRequired, match="in the App Store"):
        ClientUpgradeRequired.raise_for_version((3, 1, 0), request)

    request = Request({"Takumi-Platform-Name": "Android", "Takumi-Client-Version": "1.2.3"})
    with pytest.raises(ClientUpgradeRequired, match="in the Play Store"):
        ClientUpgradeRequired.raise_for_version((3, 1, 0), request)

    request = Request({"Takumi-Platform-Name": "MockOS", "Takumi-Client-Version": "1.2.3"})
    with pytest.raises(ClientUpgradeRequired, match=r"^((?!Store).)*$"):  # Does not contain Store
        ClientUpgradeRequired.raise_for_version((3, 1, 0), request)


def test_client_upgrade_required_sets_status_code_and_error_code():
    error = ClientUpgradeRequired((3, 1, 1), (5, 0, 0), Request({}))
    assert error.status_code == 415
    assert error.error_code == OUTDATED_CLIENT_VERSION
