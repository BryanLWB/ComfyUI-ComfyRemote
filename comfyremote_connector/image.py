"""Small static previews of an already-owned output; originals remain untouched."""
from __future__ import annotations

import io
import warnings
from pathlib import Path

from PIL import Image, ImageOps


def image_thumbnail(source: Path) -> tuple[bytes, int, int]:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(source) as original:
            if original.width * original.height > 40_000_000:
                raise ValueError("Image preview decoding limit exceeded")
            original.seek(0)
            image = ImageOps.exif_transpose(original)
            width, height = image.size
            image.thumbnail((640, 640), Image.Resampling.LANCZOS)
            # Keep the derivative single-frame VP8; composite transparency on white.
            if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                rgba = image.convert("RGBA")
                image = Image.new("RGB", image.size, "white")
                image.paste(rgba, mask=rgba.getchannel("A"))
            else:
                image = image.convert("RGB")
            for quality in (78, 65, 45):
                output = io.BytesIO()
                image.save(output, "WEBP", quality=quality, method=4)
                data = output.getvalue()
                if len(data) <= 256 * 1024:
                    return data, width, height
    raise ValueError("Image thumbnail exceeds size limit")
