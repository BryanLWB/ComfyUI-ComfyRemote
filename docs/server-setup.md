# Server Setup

Install a ComfyRemote Bridge and Worker containing connector protocol 1. The
current preview companion implementation is commit `4ebe9f9` in the local
ComfyRemote integration branch. It depends on the preceding remote management work
and is not yet part of the canonical GitHub main release. Installing only this
extension against an older server will not provide pairing endpoints.

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

Keep the previous Bridge/Worker build and a SQLite backup before upgrading. To
roll back, drain jobs, revoke the device, stop its test ComfyUI, restore the previous
Bridge and Worker, and remove only the connector-specific Access application.
