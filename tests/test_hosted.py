from unittest.mock import AsyncMock

import pytest

from comfyremote_connector.hosted import serialize_uploaded_refs
from comfyremote_connector.runtime import Runtime


def test_multi_file_conversion_preserves_order_and_rejects_silent_truncation():
    refs = [{"file": "main.png", "kind": "image"}, {"file": "aux.png", "kind": "image"}]
    assert serialize_uploaded_refs(refs, "filename_list") == ["main.png", "aux.png"]
    assert serialize_uploaded_refs(refs, "media_manifest_json") == '[{"file": "main.png", "kind": "image"}, {"file": "aux.png", "kind": "image"}]'
    with pytest.raises(ValueError):
        serialize_uploaded_refs(refs, "filename")


@pytest.mark.asyncio
async def test_browser_import_inspection_only_reads_selected_node_definitions(tmp_path):
    runtime = Runtime(tmp_path, "http://127.0.0.1:8189")
    graph = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "selected.safetensors"},
        }
    }
    runtime.hosted.api = AsyncMock(side_effect=[{"graph": graph}, {"ok": True}])
    runtime.node_info = AsyncMock(
        return_value={
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {"ckpt_name": [["selected.safetensors", "private.safetensors"]]}
                }
            }
        }
    )
    runtime.hosted.local = AsyncMock()
    await runtime.hosted.inspect_workflow("test-id")
    runtime.node_info.assert_awaited_once_with(["CheckpointLoaderSimple"])
    runtime.hosted.local.assert_not_called()
    payload = runtime.hosted.api.call_args.kwargs["json"]
    assert payload["info"]["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0] == [
        "selected.safetensors"
    ]
    assert "CheckpointLoaderSimple" in runtime.state.classes()


@pytest.mark.asyncio
async def test_browser_import_missing_nodes_reports_failure_without_generation(tmp_path):
    runtime = Runtime(tmp_path, "http://127.0.0.1:8189")
    runtime.hosted.api = AsyncMock(
        side_effect=[{"graph": {"1": {"class_type": "Missing", "inputs": {}}}}, {"ok": True}]
    )
    runtime.node_info = AsyncMock(side_effect=ValueError("Missing"))
    runtime.hosted.local = AsyncMock()
    await runtime.hosted.inspect_workflow("test-id")
    assert "error" in runtime.hosted.api.call_args.kwargs["json"]
    assert "Missing" not in runtime.state.classes()
    runtime.hosted.local.assert_not_called()


@pytest.mark.asyncio
async def test_telemetry_contains_aggregates_without_prompt_contents(tmp_path):
    hosted = Runtime(tmp_path, "http://127.0.0.1:8189").hosted
    hosted.local = AsyncMock(
        side_effect=[
            {
                "devices": [
                    {"type": "cpu"},
                    {"type": "cuda", "name": "Test GPU", "vram_total": 16000, "vram_free": 12000},
                ]
            },
            {
                "queue_running": [["private prompt"]],
                "queue_pending": [["private path"], ["other prompt"]],
            },
        ]
    )
    socket = AsyncMock()
    await hosted.send_telemetry(socket)
    socket.send_json.assert_awaited_once_with(
        {
            "type": "ping",
            "capabilities": ["multi-image-list-v1"],
            "telemetry": {
                "gpu": {"name": "Test GPU", "vram_total": 16000, "vram_free": 12000},
                "queue": {"comfy_running": 1, "comfy_pending": 2},
            },
        }
    )
    assert all(call.args[0] == "GET" for call in hosted.local.call_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [TimeoutError(), ValueError(), AttributeError()])
async def test_stats_failure_keeps_heartbeat_alive(tmp_path, failure):
    hosted = Runtime(tmp_path, "http://127.0.0.1:8189").hosted
    hosted.local = AsyncMock(side_effect=failure)
    socket = AsyncMock()
    await hosted.send_telemetry(socket)
    socket.send_json.assert_awaited_once_with({"type": "ping", "telemetry": None, "capabilities": ["multi-image-list-v1"]})


@pytest.mark.asyncio
async def test_uncertain_post_never_retries_after_restart(tmp_path):
    runtime = Runtime(tmp_path, "http://127.0.0.1:8189")
    hosted = runtime.hosted
    hosted.save("job", "submitting")
    hosted.api = AsyncMock(return_value={"id": "job", "status": "queued"})
    hosted.local = AsyncMock(side_effect=[{"queue_running": [], "queue_pending": []}, {}])
    await hosted.run_job("job")
    assert hosted.record("job")["phase"] == "uncertain"
    assert all(call.args[0] != "POST" for call in hosted.local.call_args_list)
    restarted = Runtime(tmp_path, "http://127.0.0.1:8189").hosted
    restarted.api = AsyncMock(return_value={"id": "job", "status": "queued"})
    restarted.local = AsyncMock()
    await restarted.run_job("job")
    restarted.local.assert_not_called()


@pytest.mark.asyncio
async def test_completed_task_is_not_generated_again(tmp_path):
    hosted = Runtime(tmp_path, "http://127.0.0.1:8189").hosted
    hosted.save("job", "complete", "prompt")
    hosted.api = AsyncMock(return_value={"id": "job", "status": "queued"})
    hosted.local = AsyncMock()
    await hosted.run_job("job")
    hosted.local.assert_not_called()
    assert hosted.api.call_args.kwargs["json"]["transfer_status"] == "complete"


@pytest.mark.asyncio
async def test_upload_retry_uses_recorded_outputs_without_generation(tmp_path):
    hosted = Runtime(tmp_path, "http://127.0.0.1:8189").hosted
    history = {"outputs": {"3": {"images": [{"filename": "retained.png"}]}}}
    hosted.save("job", "upload_failed", "prompt", history)
    hosted.api = AsyncMock(return_value={"id": "job", "status": "succeeded"})
    hosted.local = AsyncMock()
    hosted.upload_outputs = AsyncMock()
    await hosted.run_job("job", retry_upload=True)
    hosted.upload_outputs.assert_awaited_once()
    assert hosted.upload_outputs.call_args.args[1] == history
    hosted.local.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_before_submission_never_runs_prompt(tmp_path):
    hosted = Runtime(tmp_path, "http://127.0.0.1:8189").hosted
    hosted.api = AsyncMock(return_value={"id": "job", "status": "queued", "cancel_requested": True})
    hosted.local = AsyncMock()
    await hosted.run_job("job")
    hosted.local.assert_not_called()
    assert hosted.record("job")["phase"] == "cancelled"


@pytest.mark.asyncio
async def test_resolve_inputs_transfers_full_list_in_order_and_cleans_temporary_files(tmp_path):
    import copy
    from unittest.mock import MagicMock

    runtime = Runtime(tmp_path, "http://127.0.0.1:8189")
    runtime.pairing = {"capabilities": ["multi-image-list-v1"]}
    assets = [{"asset_id": "main", "name": "main.png", "mime": "image/png"},
              {"asset_id": "aux", "name": "aux.png", "mime": "image/png"}]
    graph = {"1": {"class_type": "ListLoader", "inputs": {"files": {"comfyremote_assets": assets, "serialization": "filename_list"}}}}
    original = copy.deepcopy(graph)
    async def chunks(_):
        yield b"isolated image bytes"
    response = MagicMock()
    response.content.iter_chunked = chunks
    context = AsyncMock()
    context.__aenter__.return_value = response
    runtime.remote = AsyncMock(return_value=context)
    runtime.hosted.local = AsyncMock(side_effect=[{"subfolder":"ComfyRemote/hosted","name":"main.png"},{"subfolder":"ComfyRemote/hosted","name":"aux.png"}])
    await runtime.hosted.resolve_inputs(graph)
    assert graph["1"]["inputs"]["files"] == ["ComfyRemote/hosted/main.png","ComfyRemote/hosted/aux.png"]
    assert [call.args[1] for call in runtime.remote.await_args_list] == ["/assets/main/content","/assets/aux/content"]
    assert not list(tmp_path.rglob("*.hosted-input"))
    assert original["1"]["inputs"]["files"]["comfyremote_assets"] == assets


@pytest.mark.asyncio
async def test_old_format_and_missing_capability_reject_before_transfer(tmp_path):
    runtime = Runtime(tmp_path, "http://127.0.0.1:8189")
    runtime.pairing = {"capabilities": []}
    runtime.remote = AsyncMock()
    assets = [{"asset_id": "main"}, {"asset_id": "aux"}]
    for extra in ({}, {"serialization":"filename_list"}, {"serialization":"unknown"}):
        graph = {"1":{"class_type":"List", "inputs":{"files":{"comfyremote_assets":assets,**extra}}}}
        with pytest.raises(ValueError):
            await runtime.hosted.resolve_inputs(graph)
    runtime.remote.assert_not_called()
