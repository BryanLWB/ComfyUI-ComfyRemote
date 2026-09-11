# ComfyRemote Connector

ComfyUI extension for pairing a machine with a ComfyRemote server, sending the
current or selected saved workflow for field review, and executing remote jobs while ComfyUI runs.

Version 0.2.0 is the first public release candidate. Registry publication and
Manager availability are recorded in [the release checklist](docs/release-0.2.0.md).
The plugin supports both self-hosted ComfyRemote and the hosted beta.
Hosted registration is subject to the website's current capacity and account rules;
the self-hosted server remains in private prerelease. Installing the plugin alone does not create a server.

The extension is independently implemented under MIT. ComfyRemote is a separate
Apache-2.0 server dependency; its account, review, job and storage services remain
on the server. No separate desktop Agent is required on the ComfyUI machine.

## Install

1. Open ComfyUI Manager / Manage Extensions and search **ComfyRemote**.
2. Confirm publisher **bryan711**. Open the version menu next to the version label,
   select **0.2.0**, then click **Install**. The search card may initially say `nightly`.
3. When installation completes and your queue is idle, apply changes to restart
   ComfyUI, then refresh the browser page to load the new frontend extension.
4. Open the **ComfyRemote** sidebar.

This fixed-version path was verified on Windows with ComfyUI 0.34.5,
frontend 1.49.6 and Python 3.13.12. The Registry version still reports `Flagged`;
successful installation does not mean that review status has been cleared.
Other Manager versions may present or restrict versions differently.
See [the installation verification](docs/manager-installation.md).

If the version menu is unavailable or installation fails, use the
[v0.2.0 release](https://github.com/BryanLWB/ComfyUI-ComfyRemote/releases/tag/v0.2.0)
ZIP in your ComfyUI installation's `custom_nodes` folder and install
`requirements.txt` using that installation's Python. Do not keep both a manual
copy and a Manager copy of the plugin. Restart ComfyUI and refresh the browser.

Use the ComfyRemote sidebar to enter your server address and a one-time pairing code.
Generate a five-digit code in ComfyRemote using the owner account; it expires after
15 minutes and works once. Older services may still issue longer codes.

Requires Windows, Python 3.12 or 3.13, and a ComfyRemote server implementing
connector protocol 1 or hosted-ws-v2. Tested with ComfyUI 0.34.5 and frontend 1.49.6. Use the local
ComfyUI browser on the device for pairing and sending; remote browser access to
these local extension controls is deliberately restricted to loopback.

For Access-protected services, the server administrator must configure a separate
device API ingress as described in [server setup](docs/server-setup.md).

## Choose and Send

The sidebar shows the current canvas and saved JSON workflows belonging to the
current ComfyUI user, including subfolders. Search or refresh the list, select one
workflow, optionally edit its name, then send it for review in ComfyRemote.
Selecting a saved file sends its latest disk contents without opening it on the
canvas. Select the current canvas to include unsaved changes instead.

The list shows each filename once, with relative paths in tooltips and accessible
names. It displays at most ten rows and scrolls internally. Sending reports progress,
success, duplicates or errors in the sidebar. Keep the owner's ComfyRemote management
page visible to receive a notification within five seconds, with a configuration link.
Duplicate execution graphs reuse the existing draft and preserve its configuration.
Registry publication is not required for connecting or sending.

Saved files are converted in an independent graph using ComfyUI's native frontend
API. Missing nodes and unsupported background conversion stop the send. Native
subgraph definitions currently require opening the workflow and sending the current
canvas. Failed conversion never substitutes a different workflow or starts generation.

The paired owner's email comes from the server. Existing pairings update
automatically; older servers show an account-unavailable placeholder. After upgrading,
restart ComfyUI and refresh its browser page; re-pairing is not required.

## Data

Sending a workflow transfers its executable graph, node titles and definitions for
the nodes it uses. It does not automatically upload the workflow library, model
weights, API keys or unrelated files. Executing a remote job transfers its inputs
and generated outputs. Device credentials are stored by the Python extension,
never returned to browser JavaScript. Unpairing revokes the server credential.
Only pair servers you trust. Installed custom nodes execute with ComfyUI's process
permissions; the connector is not a sandbox. See [privacy and limits](docs/privacy.md).

## Development

Use a dedicated ComfyUI instance. Production profiles, databases, user settings,
model files and existing custom nodes must not be edited by development scripts.
Run `python -m pytest` and `ruff check .` before a release.
