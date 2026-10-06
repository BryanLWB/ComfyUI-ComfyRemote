# 0.2.11 — hosted image previews

New hosted output images receive a static WebP preview with a longest edge of at
most 640 pixels when the paired service advertises `image-thumbnail-v1`. History
and favorites can then use the preview instead of downloading the full image.
Original images and downloads retain their full quality.

Preview uploads retry separately from successful original transfers. Their
bounded, persistent retry queue retains existing video retry journals. Services
without the image-preview capability receive no new preview uploads.

## Upgrade

The release assets are `ComfyUI-ComfyRemote-0.2.11.zip` and `SHA256SUMS.txt` on the
[GitHub release](https://github.com/BryanLWB/ComfyUI-ComfyRemote/releases/tag/v0.2.11).
Keep one connector installation, restart ComfyUI when its queue is idle, and
refresh the browser. Existing pairing is retained. The upgrade applies to new
outputs; it does not backfill previews for existing images.

GitHub publication, Registry submission and Registry approval are separate.
Manager may offer an older version while review is unresolved; check the
[Registry entry](https://registry.comfy.org/nodes/comfyremote-connector) and use
the manual release installation instructions in the README when necessary.

## Validation

The release code passed Windows CI on Python 3.12 and 3.13. Local release checks
on 2026-10-06 passed 72 Python tests, 5 Node tests and Ruff. The Windows credential
protection tests used isolated temporary data. The publication task did not
upgrade or restart a running ComfyUI installation.
