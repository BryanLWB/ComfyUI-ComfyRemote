# Updating a mobile workflow

Choose a saved workflow (or current canvas), then choose an existing mobile workflow
or **新建工作流**. After a successful send, the saved source remembers its target.
Later sends update its draft and preserve compatible phone field configuration.
Choose **新建工作流** to make another workflow instead. A changed name alone never
selects another user's or another computer's workflow.

If nodes/inputs/tool targets changed incompatibly, preview explains which fields
need correction. Existing published versions continue working until the owner tests
and publishes the updated draft. A stale revision requires refreshing the mobile
target list; the connector never silently replaces newer phone settings.

Source links live in the existing protected user's connector journal, scoped to the
service, pairing and ComfyUI user. No workflow file is modified to add tracking IDs.
Unknown/unsaved canvas sources need a target selection; Save As and renamed files
must establish their own link. If a response is lost, retry the frozen pending send;
after reopening the sidebar its pending request is offered again. This does not
re-export a changed canvas or repeat a completed creation. Unpairing clears links.

Install only one copy of this connector. The plugin reports duplicate custom_nodes
installations and its running backend version. Keep pairing/journal files in the
ComfyUI user directory when archiving an obsolete plugin folder. Restart ComfyUI
after upgrading; do not stop it during an active generation.

Requires a service advertising `workflow-update-v1` for association updates. Older
services retain ordinary imports, without pretending to preserve mobile configuration.
