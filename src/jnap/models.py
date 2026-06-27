"""Data models for the JNAP API."""

from dataclasses import dataclass, field
from enum import StrEnum


class JNAPAction(StrEnum):
    """JNAP action URIs."""

    _JNAP_BASE_URL = "http://linksys.com/jnap/"

    TRANSACTION = f"{_JNAP_BASE_URL}core/Transaction"
    GET_DEVICE_INFO = f"{_JNAP_BASE_URL}core/GetDeviceInfo"
    GET_DEVICES = f"{_JNAP_BASE_URL}devicelist/GetDevices"


@dataclass
class JNAPRequest:
    """A single action within a JNAP transaction."""

    action: JNAPAction
    request: dict = field(default_factory=dict)


@dataclass
class JNAPDevice:
    """A device seen by the router."""

    mac: str
    name: str
    ip_address: str | None = None
    hostname: str | None = None


@dataclass
class GetDeviceInfoResponse:
    """Parsed response from core/GetDeviceInfo."""

    description: str
    serial_number: str

    @classmethod
    def from_dict(cls, data: dict) -> "GetDeviceInfoResponse":
        """Parse a JNAP response dict."""
        output = data["output"]
        return cls(
            description=output["description"], serial_number=output["serialNumber"]
        )


@dataclass
class GetDevicesResponse:
    """Parsed response from devicelist/GetDevices."""

    _KNOWN_MACS = "knownMACAddresses"
    _CONNECTIONS = "connections"
    _PROPERTIES = "properties"
    _FRIENDLY_NAME = "friendlyName"
    _DEVICE_ID = "deviceID"
    _USER_DEVICE_NAME = "userDeviceName"
    _IP_ADDRESS = "ipAddress"

    devices: list[JNAPDevice]

    @classmethod
    def from_dict(cls, data: dict) -> "GetDevicesResponse":
        """Parse a JNAP response dict."""
        devices = []
        for item in data["output"]["devices"]:
            if not (macs := item.get(cls._KNOWN_MACS)):
                continue
            connections = item.get(cls._CONNECTIONS, [])
            if not connections:
                continue
            mac = macs[-1]
            hostname = item.get(cls._FRIENDLY_NAME)
            name = (
                next(
                    (
                        p["value"]
                        for p in item.get(cls._PROPERTIES, [])
                        if p["name"] == cls._USER_DEVICE_NAME
                    ),
                    None,
                )
                or hostname
                or item[cls._DEVICE_ID]
            )
            ip_address = connections[0].get(cls._IP_ADDRESS)
            devices.append(
                JNAPDevice(mac=mac, name=name, ip_address=ip_address, hostname=hostname)
            )
        return cls(devices=devices)
