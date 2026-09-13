import io
import sqlite3
from unittest.mock import AsyncMock

import av
import pytest
from PIL import Image

from comfyremote_connector.runtime import Runtime
from comfyremote_connector.video import midpoint_thumbnail


def make_video(path):
    with av.open(str(path), "w") as container:
        stream = container.add_stream("mpeg4", rate=10)
        stream.width, stream.height, stream.pix_fmt = 96, 64, "yuv420p"
        for index in range(20):
            frame = av.VideoFrame.from_image(Image.new("RGB", (96, 64), "red" if index < 10 else "blue"))
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


def test_uses_middle_frame_not_first_or_previous_keyframe(tmp_path):
    source = tmp_path / "test.mp4"
    make_video(source)
    data, width, height, duration = midpoint_thumbnail(source)
    assert (width, height, duration) == (96, 64, 2000)
    assert len(data) <= 262144
    with Image.open(io.BytesIO(data)) as image:
        red, _, blue = image.convert("RGB").getpixel((40, 30))
        assert blue > 180 and red < 60
        assert not getattr(image, "is_animated", False)


@pytest.mark.asyncio
async def test_thumbnail_failure_keeps_successful_video_and_durable_retry(tmp_path):
    runtime = Runtime(tmp_path / "state", "http://127.0.0.1:8189")
    runtime.pairing = {"origin": "https://example.test", "capabilities": ["video-thumbnail-v1"]}
    runtime.hosted.api = AsyncMock(side_effect=ValueError("quota"))
    runtime.hosted.status = AsyncMock()
    source = tmp_path / "test.mp4"
    make_video(source)
    ref = {"filename": "test.mp4", "subfolder": "", "type": "output"}
    await runtime.hosted.upload_thumbnail("asset", source, "video/mp4", ref)
    runtime.hosted.status.assert_not_called()
    with runtime.state.db() as db:
        assert db.execute("SELECT attempts FROM thumbnail_queue").fetchone()[0] == 1
    runtime.hosted.api = AsyncMock(return_value={"ready": True})
    await runtime.hosted.upload_thumbnail("asset", source, "video/mp4", ref)
    with runtime.state.db() as db:
        assert db.execute("SELECT COUNT(*) FROM thumbnail_queue").fetchone()[0] == 0
    assert runtime.hosted.api.call_args.args[0] == "PUT"


@pytest.mark.asyncio
async def test_old_service_never_receives_thumbnail_upload(tmp_path):
    runtime = Runtime(tmp_path / "state", "http://127.0.0.1:8189")
    runtime.pairing = {"origin": "https://example.test", "capabilities": ["hosted-jobs-v2"]}
    runtime.hosted.api = AsyncMock()
    await runtime.hosted.upload_thumbnail("asset", tmp_path / "absent.mp4", "video/mp4")
    runtime.hosted.api.assert_not_called()


@pytest.mark.asyncio
async def test_local_thumbnail_journal_failure_does_not_fail_original(tmp_path, monkeypatch):
    runtime = Runtime(tmp_path / "state", "http://127.0.0.1:8189")
    runtime.pairing = {"origin": "https://example.test", "capabilities": ["video-thumbnail-v1"]}
    def unavailable():
        raise sqlite3.OperationalError("synthetic disk failure")
    monkeypatch.setattr(runtime.state, "db", unavailable)
    await runtime.hosted.upload_thumbnail("asset", tmp_path / "absent.mp4", "video/mp4")
    assert runtime.hosted.thumbnail_failures
