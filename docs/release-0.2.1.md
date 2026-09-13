# 0.2.1 — midpoint video thumbnails

Prepared 2026-09-13. Publication and Manager installation are separate checks;
this source document does not claim that Registry review has completed.

Published as immutable tag `v0.2.1` at `dacff81660bc8eeeffe2018654e9184c30002061`.
Windows CI passed on Python 3.12 and 3.13 (33 tests). Manager fixed-version install,
restart, sidebar loading, pairing retention and real midpoint upload passed on
2026-09-13; see [installation evidence](manager-installation.md).
Registry status remained Pending. GitHub ZIP SHA-256:
`9e04b34d0e9a6293e89a5846329930c7d24a7b66e0f651fb966bbc0c7be833ac`.

- Compatible servers advertise `video-thumbnail-v1`. Older servers receive no new request.
- PyAV decodes forward from a keyframe to the midpoint timestamp. Pillow writes a
  static WebP, longest edge 640 px, at most 256 KiB. Unknown duration or decoding
  failure leaves a clearly unavailable preview, with the original video retained.
- New results use the existing local transfer file. Thumbnails retry separately
  from recorded local output references, at most five attempts; no workflow rerun
  or repeated upload of the original video is needed.
- Derived-image failures appear in the sidebar. Updating requires a queue-idle
  ComfyUI restart and browser refresh, preserving the existing pairing.
- Python 3.12 automated tests verify a red-first/blue-middle video, capability
  compatibility, durable retry, and failure isolation. Python 3.13 and actual
  Manager installation are recorded separately in final release evidence.

The immutable 0.2.0 tag and its assets remain available for rollback. Never install
two copies of the connector in the same ComfyUI environment.
