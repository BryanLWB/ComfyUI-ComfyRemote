# ComfyRemote Connector

ComfyUI extension for pairing a machine with a ComfyRemote server, sending the
current workflow for field review, and executing remote jobs while ComfyUI runs.

This repository is under development. Version 0.1.0 is not published or certified
for production. See [the release checklist](docs/first-release.md) for progress.

The extension is independently implemented under MIT. ComfyRemote is a separate
Apache-2.0 server dependency; its account, review, job and storage services remain
on the server. No separate desktop Agent is required on the ComfyUI machine.

## Install

Clone this repository into your test ComfyUI installation's `custom_nodes` folder,
install `requirements.txt` using that installation's Python, then restart ComfyUI.
Use the ComfyRemote sidebar to enter your server address and a one-time pairing code.
Generate pairing codes in ComfyRemote using the owner account.

## Data

Sending a workflow transfers its executable graph, node titles and definitions for
the nodes it uses. It does not automatically upload the workflow library, model
weights, API keys or unrelated files. Executing a remote job transfers its inputs
and generated outputs. Device credentials are stored by the Python extension,
never returned to browser JavaScript. Unpairing revokes the server credential.

## Development

Use a dedicated ComfyUI instance. Production profiles, databases, user settings,
model files and existing custom nodes must not be edited by development scripts.
Run `python -m pytest` and `ruff check .` before a release.
