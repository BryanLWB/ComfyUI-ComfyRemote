import time

import pytest

from comfyremote_connector.runtime import Runtime


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 404, 405])
async def test_existing_pairing_can_fetch_identity_without_exposing_token(
    tmp_path, monkeypatch, status
):
    runtime = Runtime(tmp_path, "http://127.0.0.1:8189")
    runtime.pairing = {"origin": "https://example.net", "token": "device-secret"}
    runtime.state.save_pairing(runtime.pairing)

    class Response:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        async def json(self):
            return {"owner_email": "owner@example.net"}

    Response.status = status

    async def remote(method, path, **kwargs):
        assert (method, path) == ("GET", "/identity")
        return Response()

    monkeypatch.setattr(runtime, "remote", remote)
    await runtime.refresh_identity()
    assert runtime.pairing["token"] == "device-secret"
    assert "token" not in runtime.status()
    expected = "owner@example.net" if status == 200 else None
    assert runtime.status()["owner_email"] == expected
    assert runtime.state.load_pairing().get("owner_email") == expected


@pytest.mark.asyncio
async def test_lost_submission_response_is_not_repeated_after_runtime_restart(
    tmp_path, monkeypatch
):
    calls = []

    async def local_request(self, command, source, target):
        calls.append(command["id"])
        target.write_bytes(b'{"prompt_id":"accepted"}')
        return 200, "application/json"

    async def interrupted(*args, **kwargs):
        raise OSError("Connection lost after local submission")

    monkeypatch.setattr(Runtime, "local_request", local_request)
    monkeypatch.setattr(Runtime, "remote", interrupted)
    command = {
        "id": "a" * 32,
        "method": "POST",
        "path": "/prompt",
        "size": 0,
        "expires": time.time() + 120,
        "content_type": "application/json",
    }
    with pytest.raises(OSError):
        await Runtime(tmp_path, "http://127.0.0.1:8189").execute(command)
    await Runtime(tmp_path, "http://127.0.0.1:8189").execute(command)
    assert calls == [command["id"]]


def test_invalid_saved_credential_does_not_disable_plugin(tmp_path):
    (tmp_path / "pairing.dpapi").write_bytes(b"invalid encrypted credential")
    runtime = Runtime(tmp_path, "http://127.0.0.1:8189")
    assert runtime.status()["paired"] is False
    assert "credential" in runtime.status()["error"]
