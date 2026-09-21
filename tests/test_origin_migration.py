import json

import pytest

from comfyremote_connector.origin_migration import JOURNAL, migrate, recover
from comfyremote_connector.runtime import Runtime

OLD = "https://comfy-app.dominohub.xyz"
NEW = "https://app.comfy-remote.com"


class Response:
    status = 200

    def __init__(self, data):
        self.data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        return self.data


class Session:
    def __init__(self, **changes):
        self.data = {"instance_id": "instance", "device_id": "device", "service_origin": NEW, "previous_origins": [OLD], "migration_idle": True, **changes}
        self.calls = 0

    def get(self, url, **kwargs):
        assert url == NEW + "/api/connector/identity"
        assert kwargs["allow_redirects"] is False
        assert kwargs["headers"]["Authorization"] == "Bearer device-secret"
        self.calls += 1
        return Response(self.data)


@pytest.fixture
def runtime(tmp_path):
    r = Runtime(tmp_path, "http://localhost:8188")
    r.pairing = {"origin": OLD, "token": "device-secret", "instance_id": "instance", "device_id": "device"}
    r.state.save_pairing(r.pairing)
    r.hosted.thumbnail_queue_init()
    with r.state.db() as db:
        db.execute("INSERT INTO workflow_links VALUES(?,?,?)", (r.workflow_scope("alice"), "saved.json", "workflow"))
        db.execute("INSERT INTO workflow_sends VALUES(?,?,?)", (r.workflow_scope("bob"), "request", json.dumps({"payload": {"request_id": "request"}})))
        db.execute("INSERT INTO thumbnail_queue VALUES(?,?,?,?,?)", (OLD, "asset", "{}", 2, 12))
    return r


@pytest.mark.asyncio
async def test_migration_preserves_all_users_and_retry_identity(runtime):
    scopes = [runtime.workflow_scope(user) for user in ("alice", "bob")]
    assert await migrate(runtime.state, Session())
    runtime.pairing = runtime.state.load_pairing()
    assert runtime.pairing["origin"] == NEW
    assert runtime.pairing["token"] == "device-secret"
    assert scopes == [runtime.workflow_scope(user) for user in ("alice", "bob")]
    with runtime.state.db() as db:
        assert db.execute("SELECT workflow_id FROM workflow_links WHERE scope=?", (scopes[0],)).fetchone()[0] == "workflow"
        assert db.execute("SELECT request_id FROM workflow_sends WHERE scope=?", (scopes[1],)).fetchone()[0] == "request"
        assert db.execute("SELECT origin,attempts,next_try FROM thumbnail_queue").fetchone() == (NEW, 2, 12)
    session = Session()
    assert not await migrate(runtime.state, session)
    assert session.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [{"device_id": "other"}, {"instance_id": "other"}, {"service_origin": "https://evil.example"}, {"previous_origins": []}, {"migration_idle": False}])
async def test_wrong_identity_or_busy_server_keeps_old_pairing(runtime, changes):
    assert not await migrate(runtime.state, Session(**changes))
    assert runtime.state.load_pairing()["origin"] == OLD
    assert not (runtime.state.root / JOURNAL).exists()


@pytest.mark.asyncio
async def test_interrupted_pairing_write_resumes_without_losing_queue(runtime, monkeypatch):
    save = runtime.state.save_pairing

    def fail(value):
        raise OSError("disk interruption")

    monkeypatch.setattr(runtime.state, "save_pairing", fail)
    with pytest.raises(OSError):
        await migrate(runtime.state, Session())
    assert (runtime.state.root / JOURNAL).exists()
    monkeypatch.setattr(runtime.state, "save_pairing", save)
    recover(runtime.state)
    recover(runtime.state)
    assert runtime.state.load_pairing()["origin"] == NEW
    with runtime.state.db() as db:
        assert db.execute("SELECT COUNT(*) FROM thumbnail_queue WHERE origin=?", (NEW,)).fetchone()[0] == 1


@pytest.mark.asyncio
async def test_collision_never_overwrites_existing_thumbnail_retry(runtime):
    with runtime.state.db() as db:
        db.execute("INSERT INTO thumbnail_queue VALUES(?,?,?,?,?)", (NEW, "asset", "different", 0, 0))
    with pytest.raises(ValueError, match="conflict"):
        await migrate(runtime.state, Session())
    assert runtime.state.load_pairing()["origin"] == OLD
    with runtime.state.db() as db:
        assert db.execute("SELECT COUNT(*) FROM thumbnail_queue").fetchone()[0] == 2


@pytest.mark.asyncio
async def test_unfinished_local_execution_blocks_before_remote_request(runtime):
    runtime.hosted.save("job", "uncertain")
    session = Session()
    assert not await migrate(runtime.state, session)
    assert session.calls == 0
    assert runtime.state.load_pairing()["origin"] == OLD


@pytest.mark.asyncio
async def test_unknown_customer_domain_is_never_contacted_or_rewritten(runtime):
    runtime.state.save_pairing({**runtime.pairing, "origin": "https://customer.example"})
    session = Session()
    assert not await migrate(runtime.state, session)
    assert session.calls == 0


@pytest.mark.asyncio
async def test_redirect_is_rejected_without_changing_pairing(runtime):
    class Redirect(Session):
        def get(self, url, **kwargs):
            response = super().get(url, **kwargs)
            response.status = 302
            return response

    assert not await migrate(runtime.state, Redirect())
    assert runtime.state.load_pairing()["origin"] == OLD
