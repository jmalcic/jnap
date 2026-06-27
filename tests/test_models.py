"""Tests for JNAP model from_dict parsers."""

import pytest

from jnap.models import GetDeviceInfoResponse, GetDevicesResponse, JNAPDevice


def _response(devices: list[dict]) -> dict:
    return {"result": "OK", "output": {"devices": devices}}


def _device(
    *,
    macs: list[str] = ["aa:bb:cc:dd:ee:ff"],
    connections: list[dict] = [{"ipAddress": "192.168.1.10"}],
    properties: list[dict] = [],
    device_id: str = "device-1",
    friendly_name: str | None = None,
) -> dict:
    device: dict = {
        "knownMACAddresses": macs,
        "connections": connections,
        "properties": properties,
        "deviceID": device_id,
    }
    if friendly_name is not None:
        device["friendlyName"] = friendly_name
    return device


class TestGetDeviceInfoResponseFromDict:
    def test_parses_description_and_serial_number(self) -> None:
        data = {
            "result": "OK",
            "output": {
                "description": "Velop AX4200 WiFi 6 System",
                "serialNumber": "38U10M37B21541",
            },
        }
        result = GetDeviceInfoResponse.from_dict(data)
        assert result == GetDeviceInfoResponse(
            description="Velop AX4200 WiFi 6 System",
            serial_number="38U10M37B21541",
        )


class TestGetDevicesResponseFromDict:
    def test_parses_device_mac(self) -> None:
        result = GetDevicesResponse.from_dict(_response([_device()]))
        assert result.devices[0].mac == "aa:bb:cc:dd:ee:ff"

    def test_uses_last_mac_when_multiple_present(self) -> None:
        result = GetDevicesResponse.from_dict(
            _response([_device(macs=["11:22:33:44:55:66", "aa:bb:cc:dd:ee:ff"])])
        )
        assert result.devices[0].mac == "aa:bb:cc:dd:ee:ff"

    def test_parses_ip_address_from_first_connection(self) -> None:
        result = GetDevicesResponse.from_dict(_response([_device()]))
        assert result.devices[0].ip_address == "192.168.1.10"

    def test_parses_hostname_from_friendly_name(self) -> None:
        result = GetDevicesResponse.from_dict(
            _response([_device(friendly_name="my-laptop")])
        )
        assert result.devices[0].hostname == "my-laptop"

    @pytest.mark.parametrize(
        ("device", "expected_name"),
        [
            pytest.param(
                _device(
                    properties=[{"name": "userDeviceName", "value": "My Laptop"}],
                    friendly_name="my-laptop",
                ),
                "My Laptop",
                id="user_device_name_wins",
            ),
            pytest.param(
                _device(friendly_name="my-laptop"),
                "my-laptop",
                id="friendly_name_fallback",
            ),
            pytest.param(
                _device(device_id="device-abc"),
                "device-abc",
                id="device_id_fallback",
            ),
        ],
    )
    def test_name_resolution_priority(self, device: dict, expected_name: str) -> None:
        result = GetDevicesResponse.from_dict(_response([device]))
        assert result.devices[0].name == expected_name

    def test_skips_device_with_no_mac(self) -> None:
        result = GetDevicesResponse.from_dict(_response([_device(macs=[])]))
        assert result.devices == []

    def test_skips_device_with_no_active_connection(self) -> None:
        result = GetDevicesResponse.from_dict(_response([_device(connections=[])]))
        assert result.devices == []

    def test_returns_empty_list_when_no_devices(self) -> None:
        result = GetDevicesResponse.from_dict(_response([]))
        assert result.devices == []

    def test_parses_multiple_devices(self) -> None:
        result = GetDevicesResponse.from_dict(
            _response([
                _device(macs=["aa:bb:cc:dd:ee:ff"], device_id="device-1"),
                _device(macs=["11:22:33:44:55:66"], device_id="device-2"),
            ])
        )
        assert len(result.devices) == 2
        assert result.devices[0].mac == "aa:bb:cc:dd:ee:ff"
        assert result.devices[1].mac == "11:22:33:44:55:66"

    def test_hostname_is_none_when_friendly_name_absent(self) -> None:
        result = GetDevicesResponse.from_dict(_response([_device()]))
        assert result.devices[0].hostname is None

    def test_ip_address_is_none_when_connection_has_no_ip(self) -> None:
        result = GetDevicesResponse.from_dict(
            _response([_device(connections=[{}])])
        )
        assert result.devices[0].ip_address is None
