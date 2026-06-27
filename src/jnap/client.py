"""JNAP HTTP client."""

from base64 import b64encode
from dataclasses import asdict

import aiohttp

from .exceptions import (
    JNAPError,
    JNAPInvalidInputError,
    JNAPUnauthorizedError,
    JNAPUnknownActionError,
)
from .models import GetDeviceInfoResponse, GetDevicesResponse, JNAPAction, JNAPRequest


class JNAPClient:
    """Async client for the Linksys JNAP API."""

    DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=10)
    _JNAP_HEADER = "X-JNAP-Action"
    _JNAP_AUTH_HEADER = "X-JNAP-Authorization"
    _JNAP_PATH = "/JNAP/"
    _DEFAULT_USERNAME = "admin"
    _JNAP_ERRORS: dict[str, type[JNAPError]] = {
        "_ErrorUnknownAction": JNAPUnknownActionError,
        "_ErrorUnauthorized": JNAPUnauthorizedError,
        "_ErrorInvalidInput": JNAPInvalidInputError,
    }

    def __init__(
        self,
        host: str,
        session: aiohttp.ClientSession,
        password: str,
        *,
        username: str = _DEFAULT_USERNAME,
    ) -> None:
        """Initialise the client."""
        self._url = f"http://{host}{self._JNAP_PATH}"
        self._session = session
        credentials = b64encode(f"{username}:{password}".encode()).decode()
        self._auth_header = f"Basic {credentials}"

    async def get_device_info(self) -> GetDeviceInfoResponse:
        """Return information about the router."""
        responses = await self._transaction(
            [JNAPRequest(action=JNAPAction.GET_DEVICE_INFO)]
        )
        try:
            return GetDeviceInfoResponse.from_dict(responses[0])
        except (KeyError, IndexError) as err:
            raise JNAPError("Unexpected response structure") from err

    async def get_devices(self) -> GetDevicesResponse:
        """Return all devices currently connected to the router."""
        responses = await self._transaction(
            [JNAPRequest(action=JNAPAction.GET_DEVICES, request={"sinceRevision": 0})]
        )
        try:
            return GetDevicesResponse.from_dict(responses[0])
        except (KeyError, IndexError) as err:
            raise JNAPError("Unexpected response structure") from err

    async def _transaction(self, actions: list[JNAPRequest]) -> list[dict]:
        """POST a JNAP transaction and return the responses list."""
        try:
            async with self._session.post(
                self._url,
                headers={
                    self._JNAP_HEADER: JNAPAction.TRANSACTION,
                    self._JNAP_AUTH_HEADER: self._auth_header,
                },
                json=[asdict(a) for a in actions],
                timeout=self.DEFAULT_TIMEOUT,
            ) as response:
                response.raise_for_status()
                data = await response.json()
        except aiohttp.ClientError as err:
            raise JNAPError("Communication error") from err
        result = data.get("result")
        if error_cls := self._JNAP_ERRORS.get(result):
            raise error_cls
        if result == "Error":
            response_result = data.get("responses", [{}])[0].get("result")
            if error_cls := self._JNAP_ERRORS.get(response_result):
                raise error_cls
        return data["responses"]
