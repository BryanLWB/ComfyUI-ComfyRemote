# Hosted Beta

The hosted beta requires an invited account and a current Windows ComfyUI installation.
The hosted site runs without the standalone ComfyRemote Agent.

1. Sign in at https://comfy-app.dominohub.xyz with your invited email.
2. Download the fixed-version plugin ZIP from the GitHub Release. Registry/Manager availability is recorded in release notes.
3. Extract the `ComfyUI-ComfyRemote` folder into ComfyUI's `custom_nodes` directory.
4. With the ComfyUI Python environment, install `requirements.txt` and restart ComfyUI after the queue is idle.
5. Add a computer in ComfyRemote. Enter the service address and 5-digit pairing code in the ComfyRemote sidebar. The code expires in 15 minutes and can be used only once.
6. Select the current canvas or a saved workflow and send it. Open the review link, configure fields and outputs, and publish.

Each beta account has 500,000,000 bytes of cloud space, up to two owned computers,
and one shared member per computer. Generation happens on the connected computer.
Input uploads and generated resources use the submitting account's space.

If uploading a generated result fails, the result remains on the original computer.
Free cloud space and retry the upload from task details. Keep the computer online
and retain the original output file. This action does not generate again.

If a prompt submission's result cannot be recovered after a restart, the task is
marked uncertain. Check the original ComfyUI history before submitting a new task.
The plugin does not blindly repeat a potentially accepted prompt.

Existing self-hosted pairing uses the existing protocol. This release does not
replace existing credentials or change the standalone Agent execution setting.
One plugin installation pairs with one service at a time.
