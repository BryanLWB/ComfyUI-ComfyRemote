"""Fixed project-domain migration; never accept an arbitrary remote redirect."""
from __future__ import annotations

import json

import aiohttp

from .state import protect

APPROVED_ORIGINS = {
    "https://comfy-app.dominohub.xyz": "https://app.comfy-remote.com",
    "https://comfy.dominohub.xyz": "https://selfhost.comfy-remote.com",
    "https://comfy-staging.dominohub.xyz": "https://staging.comfy-remote.com",
}
JOURNAL = "origin-migration.dpapi"


def recover(state):
    """Finish a previously verified migration before starting any connector tasks."""
    path = state.root / JOURNAL
    if not path.exists():
        return
    record = json.loads(protect(path.read_bytes(), decrypt=True))
    before, after = record["before"], record["after"]
    if APPROVED_ORIGINS.get(before["origin"]) != after["origin"]:
        raise ValueError("Unapproved pending service migration")
    expected = {**before, "origin": after["origin"], "workflow_scope_origin": before.get("workflow_scope_origin", before["origin"])}
    if after != expected or state.load_pairing() not in (before, after):
        raise ValueError("Pairing changed during service migration; manual review required")
    with state.db() as db:
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='thumbnail_queue'").fetchone()
        if exists:
            conflicts = db.execute(
                "SELECT 1 FROM thumbnail_queue a JOIN thumbnail_queue b ON a.asset_id=b.asset_id WHERE a.origin=? AND b.origin=? LIMIT 1",
                (before["origin"], after["origin"]),
            ).fetchone()
            if conflicts:
                raise ValueError("Thumbnail migration conflict; original pairing retained")
            db.execute("UPDATE thumbnail_queue SET origin=? WHERE origin=?", (after["origin"], before["origin"]))
    # The journal survives a failed atomic pairing write. Replaying the SQL is idempotent.
    state.save_pairing(after)
    path.unlink()


async def migrate(state, session):
    before = state.load_pairing()
    if not before or before.get("origin") not in APPROVED_ORIGINS:
        return False
    target = APPROVED_ORIGINS[before["origin"]]
    if not before.get("instance_id") or not before.get("device_id"):
        return False
    with state.db() as db:
        if (db.execute("SELECT 1 FROM sqlite_master WHERE name='hosted_jobs'").fetchone()
            and db.execute("SELECT 1 FROM hosted_jobs WHERE phase NOT IN ('complete','failed','cancelled') LIMIT 1").fetchone()):
            return False
    async with session.get(
        target + "/api/connector/identity",
        headers={"Authorization": "Bearer " + before["token"]},
        allow_redirects=False,
        timeout=aiohttp.ClientTimeout(total=10),
    ) as response:
        if response.status != 200:
            return False
        identity = await response.json()
    # New server explicitly attests the origin mapping and exact existing device.
    if (
        identity.get("instance_id") != before["instance_id"]
        or identity.get("device_id") != before["device_id"]
        or identity.get("service_origin") != target
        or before["origin"] not in identity.get("previous_origins", [])
        or identity.get("migration_idle") is not True
    ):
        return False
    after = {**before, "origin": target, "workflow_scope_origin": before.get("workflow_scope_origin", before["origin"])}
    pending = state.root / (JOURNAL + ".tmp")
    pending.write_bytes(protect(json.dumps({"before": before, "after": after}).encode()))
    pending.replace(state.root / JOURNAL)
    recover(state)
    return True
