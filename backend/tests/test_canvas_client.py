import httpx
from app.canvas.client import CanvasClient, parse_next_link
from app.core.config import Settings


def test_parse_next_link_supports_multiple_relations() -> None:
    header = (
        '<https://canvas.test/api/v1/courses?page=2>; rel="next", '
        '<https://canvas.test/api/v1/courses?page=1>; rel="first"'
    )
    assert parse_next_link(header) == "https://canvas.test/api/v1/courses?page=2"


async def test_client_follows_link_pagination_and_sends_bearer_token() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[{"id": 2}], headers={"X-Rate-Limit-Remaining": "100"})
        return httpx.Response(
            200,
            json=[{"id": 1}],
            headers={
                "Link": '<https://canvas.test/api/v1/courses?page=2>; rel="next"',
                "X-Rate-Limit-Remaining": "100",
            },
        )

    settings = Settings(
        canvas_base_url="https://canvas.test/api/v1",
        canvas_api_token="test-token",
        canvas_min_rate_limit_sleep_seconds=0,
    )
    transport = httpx.MockTransport(handler)
    async with CanvasClient(
        settings,
        http_client=httpx.AsyncClient(transport=transport, base_url=settings.canvas_base_url),
    ) as client:
        items = await client.get_all("/courses", params={"page": 1})

    assert items == [{"id": 1}, {"id": 2}]
    assert len(requests) == 2
    assert requests[0].headers["Authorization"] == "Bearer test-token"
    assert requests[0].headers["User-Agent"] == "AcademicOS/0.1 (Canvas integration)"


async def test_client_retries_rate_limit_response() -> None:
    attempts = 0
    sleeps: list[float] = []

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"message": "slow down"}, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    settings = Settings(canvas_base_url="https://canvas.test/api/v1", canvas_max_retries=1)
    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    transport = httpx.MockTransport(handler)
    async with CanvasClient(
        settings,
        http_client=httpx.AsyncClient(transport=transport, base_url=settings.canvas_base_url),
        sleep=fake_sleep,
    ) as client:
        response = await client.get("/courses")

    assert response.json() == {"ok": True}
    assert attempts == 2
    assert sleeps == [1]
