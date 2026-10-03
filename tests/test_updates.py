import asyncio

import pytest

from comfyremote_connector import updates


@pytest.mark.parametrize("tag,newer", [
    ("v0.2.10", True), ("v0.3.0", True), ("v1.0.0", True),
    ("v0.2.9", False), ("v0.2.8", False), ("v0.2.10-beta.1", False),
    ("nightly", False), (None, False), ("v0.2.10/../../other", False),
])
def test_only_newer_stable_versions(tag, newer):
    result = updates.release_update({"tag_name": tag, "html_url": "https://other.test"}, "0.2.9")
    assert bool(result) == newer
    if result:
        assert result["url"] == updates.RELEASE_PAGE + tag


@pytest.mark.parametrize("flag", ["draft", "prerelease"])
def test_unreleased_versions_are_not_offered(flag):
    assert updates.release_update({"tag_name": "v9.0.0", flag: True}, "0.2.9") is None


async def test_cache_concurrency_failure_and_recovery(monkeypatch):
    clock = [100.0]
    calls = []
    response = [{"tag_name": "v9.0.0"}]
    monkeypatch.setattr(updates.time, "monotonic", lambda: clock[0])

    class Response:
        async def __aenter__(self):
            await asyncio.sleep(0)
            return self

        async def __aexit__(self, *args):
            pass

        def raise_for_status(self):
            if isinstance(response[0], Exception):
                raise response[0]

        async def json(self):
            return response[0]

    class Session:
        def __init__(self, **kwargs):
            assert kwargs["timeout"].total == 8
            assert "Authorization" not in kwargs["headers"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def get(self, url, **kwargs):
            assert url == updates.RELEASE_API
            assert kwargs == {"allow_redirects": False}
            calls.append(url)
            return Response()

    monkeypatch.setattr(updates.aiohttp, "ClientSession", Session)
    checker = updates.UpdateChecker()
    first, second = await asyncio.gather(checker.check(), checker.check())
    assert first == second
    assert first["update"]["version"] == "9.0.0"
    assert len(calls) == 1
    clock[0] += 6 * 60 * 60
    response[0] = TimeoutError()
    assert await checker.check() == first
    await checker.check()
    assert len(calls) == 2
    clock[0] += 15 * 60
    response[0] = {"tag_name": "v0.1.0"}
    assert (await checker.check())["update"] is None
    assert len(calls) == 3


async def test_offline_check_does_not_break_sidebar(monkeypatch):
    class Offline:
        def __init__(self, **kwargs):
            raise OSError("offline")

    monkeypatch.setattr(updates.aiohttp, "ClientSession", Offline)
    assert (await updates.UpdateChecker().check())["update"] is None
