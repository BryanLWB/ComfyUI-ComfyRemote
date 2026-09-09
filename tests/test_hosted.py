from unittest.mock import AsyncMock

import pytest

from comfyremote_connector.runtime import Runtime


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
    socket.send_json.assert_awaited_once_with({"type": "ping", "telemetry": None})


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
