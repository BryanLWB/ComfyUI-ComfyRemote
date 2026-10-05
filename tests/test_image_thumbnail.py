import hashlib
import io
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from comfyremote_connector.image import image_thumbnail
from comfyremote_connector.runtime import Runtime


def test_bounds_preview_and_preserves_original_bytes_and_dimensions(tmp_path):
    source = tmp_path / "original.png"
    Image.effect_noise((1200, 1800), 90).convert("RGB").save(source)
    before = hashlib.sha256(source.read_bytes()).digest()
    data, width, height = image_thumbnail(source)
    assert (width, height) == (1200, 1800)
    assert len(data) <= 262144 and len(data) < source.stat().st_size / 5
    assert data[12:16] == b"VP8 "
    with Image.open(io.BytesIO(data)) as preview:
        assert preview.size == (427, 640)
        assert not getattr(preview, "is_animated", False)
        assert not preview.getexif()
    assert hashlib.sha256(source.read_bytes()).digest() == before


def test_applies_orientation_without_upscaling_or_copying_metadata(tmp_path):
    source = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private generation metadata"
    Image.new("RGB", (80, 40), "red").save(source, exif=exif)
    data, width, height = image_thumbnail(source)
    assert (width, height) == (40, 80)
    with Image.open(io.BytesIO(data)) as preview:
        assert preview.size == (40, 80)
        assert not preview.getexif()


def test_flattens_transparency_and_animation_to_a_static_webp(tmp_path):
    source = tmp_path / "transparent.png"
    Image.new("RGBA", (32, 32), (0, 0, 0, 0)).save(source)
    data, _, _ = image_thumbnail(source)
    with Image.open(io.BytesIO(data)) as preview:
        assert min(preview.convert("RGB").getpixel((0, 0))) >= 250
    source = tmp_path / "animated.gif"
    Image.new("RGB", (32, 32), "red").save(source, save_all=True, append_images=[Image.new("RGB", (32, 32), "blue")], duration=100, loop=0)
    data, _, _ = image_thumbnail(source)
    with Image.open(io.BytesIO(data)) as preview:
        assert not getattr(preview, "is_animated", False)
        assert preview.convert("RGB").getpixel((0, 0))[0] > 200


def test_invalid_or_oversized_image_cannot_start_unbounded_decoding(tmp_path):
    source = tmp_path / "invalid.png"
    source.write_bytes(b"not an image")
    with pytest.raises(OSError):
        image_thumbnail(source)
    Image.new("1", (6400, 6400)).save(source)
    with pytest.raises(ValueError, match="decoding limit"):
        image_thumbnail(source)


@pytest.mark.asyncio
async def test_image_failure_retries_independently_and_preserves_video_journal(tmp_path):
    runtime = Runtime(tmp_path / "state", "http://127.0.0.1:8189")
    pairing = {"origin": "https://example.test", "capabilities": ["image-thumbnail-v1"]}
    runtime.pairing = pairing
    with runtime.state.db() as db:
        db.execute("CREATE TABLE thumbnail_queue(origin TEXT,asset_id TEXT,source TEXT,attempts INTEGER DEFAULT 0,next_try REAL DEFAULT 0,PRIMARY KEY(origin,asset_id))")
        db.execute("INSERT INTO thumbnail_queue VALUES(?,?,?,2,42)", (pairing["origin"], "old-video", "{}"))
    source = tmp_path / "image.png"
    Image.new("RGB", (64, 48), "blue").save(source)
    runtime.hosted.api = AsyncMock(side_effect=ValueError("quota"))
    runtime.hosted.status = AsyncMock()
    ref = {"filename": "image.png", "subfolder": "", "type": "output"}
    await runtime.hosted.upload_thumbnail("image", source, "image/png", ref)
    runtime.hosted.status.assert_not_called()
    with runtime.state.db() as db:
        assert db.execute("SELECT attempts,mime FROM thumbnail_queue WHERE asset_id='image'").fetchone() == (1, "image/png")
        assert db.execute("SELECT attempts,next_try,mime FROM thumbnail_queue WHERE asset_id='old-video'").fetchone() == (2, 42, "video/mp4")
    runtime.hosted.api = AsyncMock(return_value={"ready": True})
    await runtime.hosted.upload_thumbnail("image", source, "image/png", ref)
    assert runtime.hosted.api.call_args.args[1] == "/assets/image/thumbnail?width=64&height=48"
    with runtime.state.db() as db:
        assert db.execute("SELECT COUNT(*) FROM thumbnail_queue WHERE asset_id='image'").fetchone()[0] == 0
    assert not runtime.hosted.thumbnail_failures


@pytest.mark.asyncio
async def test_old_service_does_not_receive_image_previews(tmp_path):
    runtime = Runtime(tmp_path / "state", "http://127.0.0.1:8189")
    runtime.pairing = {"origin": "https://example.test", "capabilities": ["video-thumbnail-v1"]}
    runtime.hosted.api = AsyncMock()
    await runtime.hosted.upload_thumbnail("image", tmp_path / "absent.png", "image/png")
    runtime.hosted.api.assert_not_called()
