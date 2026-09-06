# Server Setup

Install a ComfyRemote Bridge and Worker containing connector protocol 1. The
current preview companion implementation is commit `20a311c` in the local
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
and send the current workflow. Select candidate fields in ComfyRemote, save,
validate, and run an admin test. Publishing remains an explicit server operation;
replica instances cannot publish.

Keep the previous Bridge/Worker build and a SQLite backup before upgrading. To
roll back, drain jobs, revoke the device, stop its test ComfyUI, restore the previous
Bridge and Worker, and remove only the connector-specific Access application.
