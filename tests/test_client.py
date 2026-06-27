"""Tests for the JNAP client."""

from base64 import b64encode
from collections.abc import AsyncGenerator, Generator
from http import HTTPStatus

import aiohttp
import pytest
import yarl
from aioresponses import aioresponses

from jnap.client import JNAPClient
from jnap.exceptions import (
    JNAPError,
    JNAPInvalidInputError,
    JNAPUnauthorizedError,
    JNAPUnknownActionError,
)
from jnap.models import GetDeviceInfoResponse, JNAPAction

HOST = "192.168.1.1"
PASSWORD = "secret"
JNAP_URL = f"http://{HOST}/JNAP/"


def _make_response(devices: list[dict]) -> dict:
    return {"responses": [{"result": "OK", "output": {"devices": devices}}]}


def _device(
    *,
    mac: str = "aa:bb:cc:dd:ee:ff",
    connected: bool = True,
    user_name: str | None = None,
    friendly_name: str | None = None,
    device_id: str = "device-1",
) -> dict:
    device: dict = {
        "knownMACAddresses": [mac],
        "connections": [{"ipAddress": "192.168.1.10"}] if connected else [],
        "properties": (
            [{"name": "userDeviceName", "value": user_name}] if user_name else []
        ),
        "deviceID": device_id,
    }
    if friendly_name is not None:
        device["friendlyName"] = friendly_name
    return device


@pytest.fixture
def mocked() -> Generator[aioresponses, None, None]:
    with aioresponses() as m:
        yield m


@pytest.fixture
async def session() -> AsyncGenerator[aiohttp.ClientSession, None]:
    async with aiohttp.ClientSession() as s:
        yield s


@pytest.fixture
def client(session: aiohttp.ClientSession) -> JNAPClient:
    return JNAPClient(HOST, session, PASSWORD)


@pytest.mark.parametrize(
    ("device", "expected_name"),
    [
        pytest.param(
            _device(user_name="My Laptop"), "My Laptop", id="user_device_name"
        ),
        pytest.param(
            _device(friendly_name="Router Friendly"),
            "Router Friendly",
            id="friendly_name_fallback",
        ),
        pytest.param(
            _device(device_id="device-abc"), "device-abc", id="device_id_fallback"
        ),
    ],
)
async def test_get_devices_name_resolution(
    mocked: aioresponses,
    client: JNAPClient,
    device: dict,
    expected_name: str,
) -> None:
    """Test device name resolution priority: userDeviceName > friendlyName >
    deviceID."""
    mocked.post(JNAP_URL, payload=_make_response([device]))
    result = await client.get_devices()
    assert result.devices[0].name == expected_name


@pytest.mark.parametrize(
    "device",
    [
        pytest.param({**_device(), "knownMACAddresses": []}, id="no_mac"),
        pytest.param(_device(connected=False), id="not_connected"),
    ],
)
async def test_get_devices_skips(
    mocked: aioresponses,
    client: JNAPClient,
    device: dict,
) -> None:
    """Test that devices without MACs or active connections are excluded."""
    mocked.post(JNAP_URL, payload=_make_response([device]))
    result = await client.get_devices()
    assert result.devices == []


async def test_get_devices_ip_address(
    mocked: aioresponses,
    client: JNAPClient,
) -> None:
    """Test that ip_address is populated from the active connection."""
    mocked.post(JNAP_URL, payload=_make_response([_device(connected=True)]))
    result = await client.get_devices()
    assert result.devices[0].ip_address == "192.168.1.10"


async def test_get_devices_hostname(
    mocked: aioresponses,
    client: JNAPClient,
) -> None:
    """Test that hostname is taken from the friendlyName field."""
    mocked.post(JNAP_URL, payload=_make_response([_device(friendly_name="my-laptop")]))
    result = await client.get_devices()
    assert result.devices[0].hostname == "my-laptop"


async def test_get_devices_http_error(
    mocked: aioresponses,
    client: JNAPClient,
) -> None:
    """Test that HTTP errors are surfaced as JNAPError."""
    mocked.post(JNAP_URL, status=HTTPStatus.UNAUTHORIZED)
    with pytest.raises(JNAPError):
        await client.get_devices()


async def test_get_devices_bad_response(
    mocked: aioresponses,
    client: JNAPClient,
) -> None:
    """Test that an unexpected response structure raises JNAPError."""
    mocked.post(JNAP_URL, payload={"responses": []})
    with pytest.raises(JNAPError):
        await client.get_devices()


async def test_request_headers(
    mocked: aioresponses,
    client: JNAPClient,
) -> None:
    """Test that the correct JNAP action and auth headers are sent."""
    mocked.post(JNAP_URL, payload=_make_response([]))
    await client.get_devices()
    call = mocked.requests[("POST", yarl.URL(JNAP_URL))][0]
    assert call.kwargs["headers"]["X-JNAP-Action"] == JNAPAction.TRANSACTION
    assert (
        call.kwargs["headers"]["X-JNAP-Authorization"]
        == "Basic " + b64encode(b"admin:secret").decode()
    )


async def test_get_device_info_returns_description_and_serial(
    mocked: aioresponses,
    client: JNAPClient,
) -> None:
    """Test that get_device_info parses description and serial number from the
    response."""
    mocked.post(
        JNAP_URL,
        payload={
            "result": "OK",
            "responses": [
                {
                    "result": "OK",
                    "output": {
                        "manufacturer": "Linksys",
                        "modelNumber": "MX42",
                        "description": "Velop AX4200 WiFi 6 System",
                        "serialNumber": "38U10M37B21541",
                    },
                }
            ],
        },
    )
    result = await client.get_device_info()
    assert result == GetDeviceInfoResponse(
        description="Velop AX4200 WiFi 6 System", serial_number="38U10M37B21541"
    )


async def test_get_device_info_sends_correct_action(
    mocked: aioresponses,
    client: JNAPClient,
) -> None:
    """Test that get_device_info sends the GetDeviceInfo action in the transaction
    body."""
    mocked.post(
        JNAP_URL,
        payload={
            "result": "OK",
            "responses": [
                {
                    "result": "OK",
                    "output": {
                        "description": "Velop AX4200 WiFi 6 System",
                        "serialNumber": "38U10M37B21541",
                    },
                }
            ],
        },
    )
    await client.get_device_info()
    call = mocked.requests[("POST", yarl.URL(JNAP_URL))][0]
    assert call.kwargs["json"][0]["action"] == JNAPAction.GET_DEVICE_INFO


async def test_unknown_action_raises_error(
    mocked: aioresponses,
    client: JNAPClient,
) -> None:
    """Test that a top-level _ErrorUnknownAction response raises
    JNAPUnknownActionError."""
    mocked.post(JNAP_URL, payload={"result": "_ErrorUnknownAction"})
    with pytest.raises(JNAPUnknownActionError):
        await client.get_device_info()


async def test_unauthorized_raises_error(
    mocked: aioresponses,
    client: JNAPClient,
) -> None:
    """Test that _ErrorUnauthorized in responses raises JNAPUnauthorizedError."""
    mocked.post(
        JNAP_URL,
        payload={
            "result": "Error",
            "responses": [
                {
                    "result": "_ErrorUnauthorized",
                    "error": "Invalid authorization credentials",
                }
            ],
        },
    )
    with pytest.raises(JNAPUnauthorizedError):
        await client.get_devices()


async def test_invalid_input_raises_error(
    mocked: aioresponses,
    client: JNAPClient,
) -> None:
    """Test that _ErrorInvalidInput in responses raises JNAPInvalidInputError."""
    mocked.post(
        JNAP_URL,
        payload={
            "result": "Error",
            "responses": [
                {
                    "result": "_ErrorInvalidInput",
                    "error": 'Encountered unexpected member "badKey"',
                }
            ],
        },
    )
    with pytest.raises(JNAPInvalidInputError):
        await client.get_devices()


async def test_custom_username(
    mocked: aioresponses,
    session: aiohttp.ClientSession,
) -> None:
    """Test that a non-default username is encoded into the auth header."""
    custom_client = JNAPClient(HOST, session, PASSWORD, username="owner")
    mocked.post(JNAP_URL, payload=_make_response([]))
    await custom_client.get_devices()
    call = mocked.requests[("POST", yarl.URL(JNAP_URL))][0]
    assert (
        call.kwargs["headers"]["X-JNAP-Authorization"]
        == "Basic " + b64encode(b"owner:secret").decode()
    )
