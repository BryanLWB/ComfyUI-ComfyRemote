# Privacy and Limits

Pairing contacts the selected service and exchanges a single-use, five-minute code
for a device token. The Python extension stores the token with Windows DPAPI under
ComfyUI's user directory, never in browser storage. Copying this state to another
Windows account will not transfer a working credential.

Send transfers the current executable graph, node titles and relevant node
definitions. This includes prompts, defaults, referenced model names and filenames
already present in the graph. It does not upload weights, unrelated workflows or
the full model inventory. Known credential inputs and code-execution node names
are rejected, but detection is not exhaustive: inspect private graphs before sending.

Remote runs transfer their input media and generated output media. Media transfers
are limited to 512 MiB per body and use 4 MiB chunks. Existing server upload limits
may be lower. Journal state records imported node classes, graph references, submitted
prompt IDs and output ownership. Receipts are pruned after 24 hours; ownership
records remain until unpairing. Generated files follow ComfyUI and server retention.

The paired service can run installed, previously exposed node classes. Pair only
a trusted server and use trusted custom nodes. The extension restricts its HTTP
command surface; it does not sandbox Python code inside custom nodes.

After a connection loss the extension reconnects with backoff. An uncertain prompt
submission is not retried automatically because it could generate twice. Inspect
the ComfyUI queue/history and ComfyRemote job status before creating a new job.
Revocation fails closed; the server does not silently switch to another ComfyUI.

First preview limitations: Windows only, one paired device per server instance,
local-browser pairing controls, and no automatic model or node installation.
