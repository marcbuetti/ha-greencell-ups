"""Minimal client for the web server of the Green Cell "GC UPS App".

The app (Electron, Express inside) runs on the PC the UPS is plugged into via USB and,
once "HTTP server" is enabled in its settings, serves its Angular UI plus a JSON API:

    GET  /api/status                 -> "1" (no login)
    POST /api/login   {"password"}   -> 201 {"access_token": JWT, ...}
    GET  /api/current_parameters     -> measurements + flags        (Bearer)
    GET  /api/nominal_parameters     -> rated values                (Bearer)
    GET  /api/device/specification   -> model, power, capacity, ... (Bearer)
    GET  /api/data                   -> manufacturer, vendor, protocol (Bearer)
    POST /api/commands {"action": "<name>Order", "args": {}}       (Bearer)

Pitfalls measured on a real installation:
* The login body schema is strict: any extra key (e.g. "username") gives 403, a wrong
  password 401. There is no user name at all.
* The HTTP payload is camelCase (batteryLevel, utilityFail); the snake_case names in the
  UI bundle (battery_level, is_utility_fail) are route names. Both are accepted here.
* Negative numbers mean "unknown" (no temperature probe, no USB link) and become None.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp

DEFAULT_PORT = 8080
TIMEOUT = 10


class GCUPSError(Exception):
    """Generic API error."""


class GCUPSConnectionError(GCUPSError):
    """App not reachable (PC off, HTTP server disabled, wrong port)."""


class GCUPSAuthError(GCUPSError):
    """Password rejected."""


def normalize_host(host: str, port: int | None = None) -> str:
    """'10.0.0.5' -> 'http://10.0.0.5:8080'; keeps an explicit scheme/port."""
    host = host.strip().rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"
    scheme, _, rest = host.partition("://")
    hostpart = rest.split("/", 1)[0]
    # IPv6 literal "[::1]" or "[::1]:8080"
    has_port = hostpart.rsplit("]", 1)[-1].count(":") == 1 if "[" in hostpart else ":" in hostpart
    if not has_port:
        hostpart = f"{hostpart}:{port or DEFAULT_PORT}"
    return f"{scheme}://{hostpart}"


class GCUPSApi:
    """Read-mostly client. Keeps the JWT until the app rejects it, then logs in once more."""

    def __init__(self, session: aiohttp.ClientSession, host: str, password: str) -> None:
        self.host = normalize_host(host)
        self._session = session
        self._password = password
        self._token: str | None = None
        self._lock = asyncio.Lock()

    async def _raw(
        self, method: str, path: str, *, payload: Any = None, auth: bool = True
    ) -> tuple[int, Any]:
        headers = {"Accept": "application/json"}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with asyncio.timeout(TIMEOUT):
                async with self._session.request(
                    method, f"{self.host}/api{path}", headers=headers, json=payload
                ) as resp:
                    text = await resp.text()
                    status = resp.status
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise GCUPSConnectionError(f"{path}: {err!r}") from err
        try:
            body: Any = json.loads(text)
        except ValueError:
            body = text
        return status, body

    async def status(self) -> bool:
        """Unauthenticated liveness probe (answers '1')."""
        status, body = await self._raw("GET", "/status", auth=False)
        return status == 200 and str(body).strip() in ("1", "true")

    async def login(self) -> None:
        # Exactly one key - the app rejects anything else with 403.
        status, body = await self._raw(
            "POST", "/login", payload={"password": self._password}, auth=False
        )
        if status in (401, 403):
            raise GCUPSAuthError(f"login -> {status}")
        if status >= 400:
            raise GCUPSError(f"login -> {status}")
        token = None
        if isinstance(body, dict):
            token = body.get("access_token") or body.get("accessToken") or body.get("jwt")
        elif isinstance(body, str) and body.count(".") == 2:
            token = body.strip()
        if not token:
            raise GCUPSError("login: no access_token in response")
        self._token = token

    async def _get(self, path: str, *, method: str = "GET", payload: Any = None) -> Any:
        async with self._lock:
            if self._token is None:
                await self.login()
            status, body = await self._raw(method, path, payload=payload)
            if status in (401, 403):
                # Token expired or the app restarted (invalidates all tokens silently).
                self._token = None
                await self.login()
                status, body = await self._raw(method, path, payload=payload)
                if status in (401, 403):
                    raise GCUPSAuthError(f"{path} -> {status}")
        if status >= 400:
            raise GCUPSError(f"{path} -> {status}")
        return body

    async def current_parameters(self) -> dict[str, Any]:
        body = await self._get("/current_parameters")
        if not isinstance(body, dict):
            raise GCUPSError("current_parameters: unexpected payload")
        return body

    async def nominal_parameters(self) -> dict[str, Any]:
        body = await self._get("/nominal_parameters")
        return body if isinstance(body, dict) else {}

    async def specification(self) -> dict[str, Any]:
        body = await self._get("/device/specification")
        return body if isinstance(body, dict) else {}

    async def device_data(self) -> dict[str, Any]:
        body = await self._get("/data")
        return body if isinstance(body, dict) else {}

    async def command(self, action: str, args: dict[str, Any] | None = None) -> Any:
        """POST /api/commands - only '*Order' actions are accepted by the app."""
        if not action.endswith("Order"):
            raise ValueError(action)
        return await self._get(
            "/commands", method="POST", payload={"action": action, "args": args or {}}
        )
