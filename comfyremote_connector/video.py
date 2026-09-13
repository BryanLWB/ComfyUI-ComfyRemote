"""Bounded midpoint extraction from a local, already-owned generated video."""
from __future__ import annotations

import io
import math
from pathlib import Path

import av
from PIL import Image


def midpoint_thumbnail(source: Path) -> tuple[bytes, int, int, int]:
    with av.open(str(source), mode="r") as container:
        stream = next((s for s in container.streams if s.type == "video"), None)
        if stream is None or not stream.time_base:
            raise ValueError("Video timeline is unavailable")
        duration = (
            float(stream.duration * stream.time_base) if stream.duration is not None
            else float(container.duration / av.time_base) if container.duration else 0
        )
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Video duration is unavailable")
        start = stream.start_time or 0
        target = start + int(duration / 2 / float(stream.time_base))
        container.seek(target, stream=stream, backward=True, any_frame=False)
        chosen = None
        for index, frame in enumerate(container.decode(stream)):
            if index >= 1200:
                raise ValueError("Video midpoint decoding limit exceeded")
            if frame.pts is not None and frame.pts >= target:
                chosen = frame
                break
        if chosen is None:
            raise ValueError("Video midpoint could not be decoded")
        width, height = chosen.width, chosen.height
        image = chosen.to_image().convert("RGB")
        image.thumbnail((640, 640), Image.Resampling.LANCZOS)
        for quality in (80, 65, 45):
            output = io.BytesIO()
            image.save(output, "WEBP", quality=quality, method=4)
            if len(output.getvalue()) <= 256 * 1024:
                return output.getvalue(), width, height, round(duration * 1000)
        raise ValueError("Video thumbnail exceeds size limit")
