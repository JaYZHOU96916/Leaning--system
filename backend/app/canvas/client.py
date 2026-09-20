import asyncio
import email.utils
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings, get_settings


class CanvasAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"Canvas API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message


def parse_next_link(link_header: str | None) -> str | None:
    """Extract the RFC 5988 ``rel=next`` URL from a Link header."""

    if not link_header:
        return None
    for match in re.finditer(r"<([^>]+)>\s*;\s*([^,]+)", link_header):
        target, parameters = match.groups()
        relations = re.search(r"(?:^|;)\s*rel\s*=\s*(?:\"([^\"]+)\"|([^;\s]+))", parameters)
        if relations:
            relation_value = relations.group(1) or relations.group(2) or ""
            if "next" in relation_value.split():
                return target
    return None


class CanvasClient:
    """Resilient async Canvas client with pagination and adaptive throttling."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.settings = settings or get_settings()
        self._client = http_client or httpx.AsyncClient(
            base_url=self.settings.canvas_base_url,
            timeout=self.settings.canvas_request_timeout_seconds,
            headers=self._build_headers(),
        )
        if http_client is not None:
            self._client.headers.update(self._build_headers())
        self._owns_client = http_client is None
        self._sleep = sleep

    def _build_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.settings.canvas_token_value:
            headers["Authorization"] = f"Bearer {self.settings.canvas_token_value}"
        return headers

    async def __aenter__(self) -> "CanvasClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float:
        if not value:
            return 0.0
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_at = email.utils.parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return 0.0

    async def _throttle_from_response(self, response: httpx.Response) -> None:
        raw_remaining = response.headers.get("X-Rate-Limit-Remaining")
        if raw_remaining is None:
            return
        try:
            remaining = float(raw_remaining)
        except ValueError:
            return
        minimum = self.settings.canvas_min_rate_limit_sleep_seconds
        maximum = self.settings.canvas_max_rate_limit_sleep_seconds
        if remaining <= 0:
            delay = maximum
        elif remaining < 2:
            delay = max(minimum, 1.0)
        elif remaining < 5:
            delay = max(minimum, 0.5)
        else:
            delay = 0.0
        if delay > 0:
            await self._sleep(min(delay, maximum))

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_response: httpx.Response | None = None
        max_attempts = max(1, self.settings.canvas_max_retries + 1)
        for attempt in range(max_attempts):
            response = await self._client.request(method, url, **kwargs)
            last_response = response
            if response.status_code not in {429, 500, 502, 503, 504}:
                await self._throttle_from_response(response)
                if response.is_error:
                    raise CanvasAPIError(response.status_code, self._error_message(response))
                return response

            if attempt == max_attempts - 1:
                break
            backoff = min(2**attempt, self.settings.canvas_max_rate_limit_sleep_seconds)
            retry_after = self._retry_after_seconds(response.headers.get("Retry-After"))
            delay = min(
                max(backoff, retry_after),
                self.settings.canvas_max_rate_limit_sleep_seconds,
            )
            await self._sleep(delay)

        assert last_response is not None
        raise CanvasAPIError(last_response.status_code, self._error_message(last_response))

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, Mapping):
                return str(payload.get("message") or payload.get("errors") or payload)
            return str(payload)
        except ValueError:
            return response.text[:500] or response.reason_phrase

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def iter_pages(self, url: str, **kwargs: Any) -> AsyncIterator[httpx.Response]:
        next_url: str | None = url
        request_kwargs = dict(kwargs)
        while next_url:
            response = await self.get(next_url, **request_kwargs)
            yield response
            next_url = parse_next_link(response.headers.get("Link"))
            request_kwargs.pop("params", None)

    async def get_all(self, url: str, **kwargs: Any) -> list[Any]:
        items: list[Any] = []
        async for response in self.iter_pages(url, **kwargs):
            payload = response.json()
            if isinstance(payload, list):
                items.extend(payload)
            else:
                items.append(payload)
        return items

    async def download_to_path(
        self,
        url: str,
        destination: Path,
        *,
        chunk_size: int = 1024 * 1024,
    ) -> int:
        """Stream a Canvas file to disk without buffering the whole file in memory."""

        destination.parent.mkdir(parents=True, exist_ok=True)
        async with self._client.stream("GET", url) as response:
            if response.is_error:
                raise CanvasAPIError(response.status_code, self._error_message(response))
            await self._throttle_from_response(response)
            size = 0
            with destination.open("wb") as output:
                async for chunk in response.aiter_bytes(chunk_size):
                    output.write(chunk)
                    size += len(chunk)
            return size
