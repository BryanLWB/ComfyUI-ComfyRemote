# Server Setup

Use a ComfyRemote Bridge and Worker that both implement connector protocol 1,
including the identity and import-event routes described below. The unified
plugin also negotiates hosted-ws-v2 with a compatible hosted service. Pairing
does not change the self-hosted Agent's execution transport. Confirm the service
version before upgrading; installing a plugin alone does not add server endpoints.

For Cloudflare deployments, preserve website login and protected Bridge ingress.
Create one separate self-hosted Access application for the service origin's
`/api/connector/*` path with a Bypass policy. This path uses device bearer
authentication instead of browser login. Never bypass the entire site or Bridge.
The Worker forwards only allowlisted connector routes with its Bridge service
credential; no Cloudflare token is installed on the ComfyUI machine.

In ComfyRemote owner settings, generate a pairing code. In ComfyUI, open the
ComfyRemote sidebar and enter the service origin and code. Once connected, name
and send the current canvas or a selected saved workflow. Select candidate fields in ComfyRemote, save,
validate, and run an admin test. Publishing remains an explicit server operation;
replica instances cannot publish.

Version 0.1.1 adds device-authenticated `GET /api/connector/identity` and optional
`owner_email` in pairing responses. Allowlist this GET route in the Worker while
preserving bearer authentication. Existing devices backfill the owner identity;
older services returning 404 or 405 remain usable without an email display.

Version 0.1.2 requires migration `0015_connector_import_events` for persistent receive
events. Owner-only `GET /admin/api/connector/imports` (remote management alias:
`/api/manage/connector/imports`) accepts an optional `after` event cursor. Omitting it
establishes a baseline without replaying old notifications. Both new and duplicate
imports record metadata only: event ID, workflow ID, version, name, time and duplicate
flag. Management polling pauses when hidden and never reloads an active editor.
New imports select supported Save outputs and VHS outputs with saving enabled.
Existing drafts, duplicates and published versions retain their chosen outputs.

Keep the previous Bridge/Worker build and a SQLite backup before upgrading. To
roll back, drain jobs, revoke the device, stop its test ComfyUI, restore the previous
Bridge and Worker, and remove only the connector-specific Access application.
