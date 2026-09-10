# ComfyRemote plugin 0.2.0

Publisher: `bryan711`. Registry node ID: `comfyremote-connector` (availability must
be checked before publication). Repository license: MIT. Windows, Python 3.12/3.13.

## Release gates

- [x] Publisher confirmed by the owner.
- [ ] Python and browser compatibility validation for this release.
- [ ] Audit all reachable Git history and old release attachments before public visibility.
- [ ] End-to-end isolated self-hosted installation and generation.
- [ ] Public GitHub tag/release and Registry upload.
- [ ] Registry indexed and ComfyUI Manager search/install verified.

Do not interpret prepared metadata as an available Registry release. If indexing
is pending, use the fixed-version ZIP attached to the eventual GitHub release.
Self-hosted ComfyRemote remains private; hosted accounts require an invitation.

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
File failures made no workflow send request. Filesystem enumeration and fresh
Manager installation still require their final release acceptance.

Self-hosted single-card UI passed desktop/390px/320px checks; pairing issue and
cancellation were exercised in a browser. GitHub Python 3.12 and 3.13 checks passed.
Real phone and clean Windows acceptance remain pending. Registry/Manager is not yet published.
