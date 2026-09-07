# Changelog

## 0.1.1 - Private Preview

- Search and send a saved workflow from the current user's ComfyUI folder, including subfolders.
- Convert saved files without changing the canvas, open tabs, unsaved edits or undo history.
- Show server-provided owner email and a compact connection header with confirmed unpairing.
- Backfill identity on existing pairings without returning device credentials to the browser.
- Companion management fix: added candidate fields render and expand immediately; edits survive network failures.
- Distinguish expired login, uncertain connection failures and actual Bridge errors.
- Verify real Krea/H3 duplicate imports on staging while preserving existing field configurations.

Native subgraph files require current-canvas sending. Public Registry publication remains pending.

## 0.1.0 - Private Preview

- Pair a Windows ComfyUI device with a configurable ComfyRemote service.
- Send current workflows as private drafts with selectable field candidates.
- Execute jobs through outbound HTTPS, with progress and chunked media transfers.
- Protect device credentials with DPAPI and prevent replay of submitted commands.
- Add a lightweight ComfyUI sidebar and staging image/video acceptance coverage.

Requires the companion server integration; Registry publication is pending.
