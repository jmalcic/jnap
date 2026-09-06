# jnap

Async Python client for the [Linksys JNAP API](http://linksys.com/jnap/).

## Installation

```
pip install jnap
```

## Usage

```python
import asyncio
import aiohttp
from jnap import JNAPClient

async def main():
    async with aiohttp.ClientSession() as session:
        client = JNAPClient("192.168.1.1", session, password="your-password")

        info = await client.get_device_info()
        print(info.description, info.serial_number)

        response = await client.get_devices()
        for device in response.devices:
            print(device.name, device.mac, device.ip_address)

asyncio.run(main())
```

## API

### `JNAPClient(host, session, password=None, *, username="admin")`

The main client class. Accepts an existing `aiohttp.ClientSession` so you can manage connection pooling and lifecycle yourself. If `password` is omitted, requests are sent without authorization, for routers that don't require it.

#### Methods

- `await client.get_device_info()` → `GetDeviceInfoResponse`  
  Returns the router's description and serial number.

- `await client.get_devices()` → `GetDevicesResponse`  
  Returns all devices currently connected to the router. Only devices with a known MAC address and an active connection are included.

### Models

| Class | Fields |
|---|---|
| `GetDeviceInfoResponse` | `description`, `serial_number` |
| `GetDevicesResponse` | `devices: list[JNAPDevice]` |
| `JNAPDevice` | `mac`, `name`, `ip_address`, `hostname` |

Device names are resolved in priority order: user-assigned name → friendly name → device ID.

### Exceptions

All exceptions inherit from `JNAPError`.

| Exception | Raised when |
|---|---|
| `JNAPUnauthorizedError` | Authentication failed |
| `JNAPUnknownActionError` | The device does not recognise the action |
| `JNAPInvalidInputError` | The request was rejected as invalid |

## License

MIT
