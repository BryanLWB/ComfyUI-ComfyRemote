import json

import pytest

from comfyremote_connector.runtime import Runtime


class Response:
    status = 200

    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        return self.value


@pytest.mark.asyncio
async def test_source_association_is_scoped_and_survives_restart(tmp_path, monkeypatch):
    r = Runtime(tmp_path, "http://localhost:8195")
    r.pairing = {"origin": "https://example.test", "instance_id": "instance", "device_id": "device", "capabilities": ["workflow-update-v1"]}

    async def refresh():
        pass

    async def remote(method, path, **kwargs):
        return Response({"workflows": [{"workflow_id": "mobile", "revision": 2}]})

    monkeypatch.setattr(r, "refresh_identity", refresh)
    monkeypatch.setattr(r, "remote", remote)
    r.finish_workflow(r.workflow_scope("alice"), "folder/example.json", "request", {"workflow_id": "mobile"})
    assert (await r.workflow_targets("alice", "folder/example.json"))["linked_workflow_id"] == "mobile"
    assert (await r.workflow_targets("bob", "folder/example.json"))["linked_workflow_id"] is None
    assert (await r.workflow_targets("alice", "other/example.json"))["linked_workflow_id"] is None
    r2 = Runtime(tmp_path, "http://localhost:8195")
    r2.pairing = dict(r.pairing)
    monkeypatch.setattr(r2, "refresh_identity", refresh)
    monkeypatch.setattr(r2, "remote", remote)
    assert (await r2.workflow_targets("alice", "folder/example.json"))["linked_workflow_id"] == "mobile"
    r2.pairing["device_id"] = "repaired"
    assert (await r2.workflow_targets("alice", "folder/example.json"))["linked_workflow_id"] is None
    r.state.clear_pairing()
    assert (await r.workflow_targets("alice", "folder/example.json"))["linked_workflow_id"] is None


@pytest.mark.asyncio
async def test_uncertain_send_retries_exact_payload_without_reexport_or_inspection(tmp_path, monkeypatch):
    r = Runtime(tmp_path, "http://localhost:8195")
    r.pairing = {"origin": "https://example.test", "instance_id": "instance", "device_id": "device"}
    payload = {"request_id": "same", "name": "保留", "prompt": {"1": {"inputs": {"text": "原内容"}}}}
    scope = r.workflow_scope("alice")
    with r.state.db() as db:
        db.execute("INSERT INTO workflow_sends VALUES(?,?,?)", (scope, "same", json.dumps({"source": "saved.json", "payload": payload})))

    async def remote(method, path, **kwargs):
        assert kwargs["json"] == payload
        return Response({"workflow_id": "mobile", "revision": 3})

    monkeypatch.setattr(r, "remote", remote)
    with pytest.raises(ValueError, match="没有待重试"):
        await r.retry_workflow("same", "bob")
    assert (await r.retry_workflow("same", "alice"))["revision"] == 3
    with r.state.db() as db:
        assert db.execute("SELECT COUNT(*) FROM workflow_sends").fetchone()[0] == 0
        assert db.execute("SELECT workflow_id FROM workflow_links").fetchone()[0] == "mobile"
