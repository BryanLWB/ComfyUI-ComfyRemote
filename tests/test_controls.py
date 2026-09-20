import json
from pathlib import Path

import pytest

from comfyremote_connector.controls import (
    compile_controls,
    control_candidates,
    validate_control_manifest,
)
from comfyremote_connector.runtime import Runtime


def test_native_comfyui_graph_conversion():
    samples = json.loads((Path(__file__).parent / "fixtures/native-control-fixtures.json").read_text(encoding="utf-8"))
    for sample in samples:
        p = sample["payload"]
        manifest = validate_control_manifest(p["control_manifest"], p["prompt"])
        fields = control_candidates(manifest)
        assert compile_controls(p["prompt"], manifest, [], {}) == p["original_prompt"]
        for s in sample["states"]:
            assert compile_controls(p["prompt"], manifest, fields, {fields[0]["key"]: s["enabled"]}) == s["prompt"]


@pytest.mark.asyncio
async def test_old_service_rejects_control_import_without_silent_drop(tmp_path, monkeypatch):
    sample = json.loads((Path(__file__).parent / "fixtures/native-control-fixtures.json").read_text(encoding="utf-8"))[0]
    runtime = Runtime(tmp_path, "http://127.0.0.1:8194")
    runtime.pairing = {"capabilities": []}

    async def identity():
        pass

    monkeypatch.setattr(runtime, "refresh_identity", identity)
    with pytest.raises(ValueError, match="先更新"):
        await runtime.send_workflow({**sample["payload"], "name": "Test"})


@pytest.mark.asyncio
async def test_native_conversion_mismatch_prevents_upload(tmp_path, monkeypatch):
    sample = json.loads((Path(__file__).parent / "fixtures/native-control-fixtures.json").read_text(encoding="utf-8"))[0]
    runtime = Runtime(tmp_path, "http://127.0.0.1:8194")
    runtime.pairing = {"capabilities": ["workflow-controls-v1"]}

    async def identity():
        pass

    monkeypatch.setattr(runtime, "refresh_identity", identity)
    with pytest.raises(ValueError, match="不一致"):
        await runtime.send_workflow({**sample["payload"], "name": "Test", "original_prompt": sample["payload"]["prompt"]})


def test_diagnostics_cannot_add_controls_or_foreign_nodes():
    from comfyremote_connector.control_diagnostics import validate_control_diagnostics
    sample = json.loads((Path(__file__).parent / "fixtures/native-control-fixtures.json").read_text(encoding="utf-8"))[0]["payload"]
    manifest = sample["control_manifest"]
    issue = {"node_id": manifest["nodes"][0]["id"], "group_id": "g_9", "group_label": "输入", "code": "parent_group", "reason": "请使用小分组开关", "related_node_ids": []}
    assert validate_control_diagnostics([issue], manifest) == [issue]
    for change in [{"node_id": "999999"}, {"node_id": []}, {"reason": "bad\ntext"}, {"related_node_ids": ["../file"]}, {"members": ["9"]}]:
        with pytest.raises(ValueError):
            validate_control_diagnostics([{**issue, **change}], manifest)
    assert validate_control_diagnostics(None, manifest) == []
