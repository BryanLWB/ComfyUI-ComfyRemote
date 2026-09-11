# ComfyRemote plugin 0.2.0

Publisher: `bryan711`. Registry node ID: `comfyremote-connector`. Repository license: MIT. Windows, Python 3.12/3.13.

## Release gates

- [x] Publisher confirmed by the owner.
- [x] Python and browser compatibility validation for this release.
- [x] Clean public history checked; original PRs and preview attachments remain in a separate private archive.
- [x] Isolated packaged self-hosted service and real image/video/audio generation. Public Tunnel and physical-phone acceptance remain pending.
- [x] Public GitHub tag/release and Registry upload (2026-09-10).
- [x] ComfyUI Manager search and explicit 0.2.0 installation verified (2026-09-11).
- [ ] Registry Flagged reason clarified and default latest listing corrected.

Manager installation using its explicit 0.2.0 version selector, restart, sidebar,
local pairing and workflow import passed. The Registry still reports Flagged and
the search card initially shows nightly; see [installation verification](manager-installation.md).
Self-hosted ComfyRemote remains private; hosted signup follows current website capacity.

A release must match its tag and a reviewed main-branch commit. Never overwrite
an existing Registry version. Store publishing credentials only in the GitHub
REGISTRY_ACCESS_TOKEN secret. Do not include tokens in source, archives or logs.
## Phase 2 candidate validation

On 2026-09-10 the isolated Windows installer and its packaged service completed
real image (PNG), video (MP4) and audio (FLAC) test generation through this plugin.
All three workflows imported, validated, produced local media and published in the
isolated database. No production instance, credentials or existing canvas was changed.

The sidebar loaded in ComfyUI 0.34.5 / frontend 1.49.6. Selected-file import and
repeat import preserved a dirty canvas, active tab, open tabs and nonempty undo/redo
history. Chinese same-name paths, latest file contents, more than ten entries,
missing file and missing node failures were checked using local fixture responses.
File failures made no workflow send request. Filesystem enumeration still requires its final release acceptance.
Fresh Manager installation was subsequently verified as recorded above.

Self-hosted single-card UI passed desktop/390px/320px checks; pairing issue and
cancellation were exercised in a browser. GitHub Python 3.12 and 3.13 checks passed.
Real phone and clean Windows acceptance remain pending. Explicit fixed-version Manager installation passed on the existing isolated Windows test environment.

## Public archive boundary

The public repository contains sanitized main history only. Earlier private preview
PRs and release attachments were not migrated. Registry configuration validates with
comfy-cli 1.20.0; the archive excludes test tools and operational documents.

## Registry upload result

- [Publishing workflow](https://github.com/BryanLWB/ComfyUI-ComfyRemote/actions/runs/34427514013): success.
- [Registry node](https://registry.comfy.org/nodes/comfyremote-connector): active node owned by bryan711.
- Version 0.2.0: NodeVersionStatusPending on initial verification; no download URL.
- 2026-09-11: Manager explicit-version search/install passed; Registry status remains Flagged without a diagnostic reason.
- No version number was overwritten or incremented to bypass platform processing.
