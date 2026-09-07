# ComfyRemote Connector

ComfyUI extension for pairing a machine with a ComfyRemote server, sending the
current or selected saved workflow for field review, and executing remote jobs while ComfyUI runs.

Version 0.1.1 is a private self-use preview, verified against a staging ComfyRemote
instance. Public Registry publication is pending publisher identity. See
[the release checklist](docs/first-release.md) and [acceptance results](docs/acceptance.md).

The extension is independently implemented under MIT. ComfyRemote is a separate
Apache-2.0 server dependency; its account, review, job and storage services remain
on the server. No separate desktop Agent is required on the ComfyUI machine.

## Install

Clone this repository into your test ComfyUI installation's `custom_nodes` folder,
install `requirements.txt` using that installation's Python, then restart ComfyUI.
Use the ComfyRemote sidebar to enter your server address and a one-time pairing code.
Generate pairing codes in ComfyRemote using the owner account.

Requires Windows, Python 3.12 or 3.13, and a ComfyRemote server implementing
connector protocol 1. Tested with ComfyUI 0.34.5 and frontend 1.49.6. Use the local
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
