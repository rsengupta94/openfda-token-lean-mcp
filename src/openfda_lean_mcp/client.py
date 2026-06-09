"""Async openFDA HTTP client — transport only.

Responsibilities: build the request, apply a timeout, attach an optional API key,
back off on 429, and parse the envelope. Response *shaping* (projection, aggregation,
curation, meta-strip) is the shaper's job (Phase 1) — this layer stays thin and returns
``{"results": [...], "meta": {...}}`` for both search and count.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from .fields import BASE_URL, ENDPOINTS
from .query import validate_endpoint

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
MAX_RETRIES = 3


class OpenFDAError(RuntimeError):
    """A non-recoverable openFDA API response (after retries)."""


def _parse(status_code: int, body: dict[str, Any] | None) -> dict[str, Any]:
    """Map an openFDA HTTP response to ``{"results", "meta"}`` (sync + testable).

    A 404 with error code NOT_FOUND means "zero matches" — openFDA's normal way of
    signalling an empty result set — so it is returned as empty, not raised.
    """
    if status_code == 404 and isinstance(body, dict):
        if (body.get("error") or {}).get("code") == "NOT_FOUND":
            return {"results": [], "meta": body.get("meta") or {}}
    if status_code != 200 or not isinstance(body, dict):
        code = (body.get("error") or {}).get("code") if isinstance(body, dict) else None
        raise OpenFDAError(
            f"openFDA returned HTTP {status_code}" + (f" ({code})" if code else "")
        )
    return {"results": body.get("results", []), "meta": body.get("meta", {})}


class OpenFDAClient:
    """Async client for the three openFDA drug endpoints.

    Use as an async context manager so the underlying ``httpx.AsyncClient`` is closed::

        async with OpenFDAClient() as c:
            await c.search("label", search='openfda.generic_name:"ibuprofen"')
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        base_url: str = BASE_URL,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENFDA_API_KEY")
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._client = client          # injectable for tests
        self._owns_client = client is None

    async def __aenter__(self) -> "OpenFDAClient":
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        validate_endpoint(endpoint)
        if self._client is None:
            raise OpenFDAError("client not started; use 'async with OpenFDAClient() as c:'")
        url = f"{self._base_url}/{ENDPOINTS[endpoint]}.json"
        q = {k: v for k, v in params.items() if v is not None}
        if self._api_key:
            q["api_key"] = self._api_key

        delay = 1.0
        resp = None
        for attempt in range(MAX_RETRIES):
            resp = await self._client.get(url, params=q)
            if resp.status_code == 429 and attempt < MAX_RETRIES - 1:
                await asyncio.sleep(float(resp.headers.get("retry-after", delay)))
                delay *= 2
                continue
            break

        try:
            body = resp.json()
        except ValueError:
            body = None
        return _parse(resp.status_code, body)

    async def search(
        self, endpoint: str, *, search: str | None = None, limit: int = 10, skip: int = 0
    ) -> dict[str, Any]:
        """Run a search and return projected-record-ready ``{"results", "meta"}``."""
        return await self._request(
            endpoint, {"search": search, "limit": limit, "skip": skip}
        )

    async def count(
        self,
        endpoint: str,
        count_field: str,
        *,
        search: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Run a ``count`` aggregation; ``results`` is ``[{"term", "count"}, ...]``."""
        return await self._request(
            endpoint, {"search": search, "count": count_field, "limit": limit}
        )
