import time

import pytest

from comfyremote_connector.runtime import Runtime


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
