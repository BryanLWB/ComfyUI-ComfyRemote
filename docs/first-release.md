# First release

## Accepted scope

- Private GitHub repository BryanLWB/ComfyUI-ComfyRemote; MIT; independent code.
- One ComfyUI machine paired to one ComfyRemote instance using an expiring code.
- Configurable service origin; Windows first; ComfyUI owns connector lifecycle.
- Server retains accounts, review, persistent job queue and asset storage.
- Device requires no separate Agent, public ComfyUI port or Cloudflare credentials.
- Small sidebar: owner identity, connection, pairing, saved-workflow selection, name, send and error.
- API workflow conversion uses ComfyUI's frontend API. Missing nodes block sending.
- Draft field candidates cover scalar controls, image/video/audio and multiple media.
- Owner reviews, validates, tests and publishes using ComfyRemote.
- Real image and video acceptance; automated audio/multi-media contract coverage.
- Staging self-use first, followed by public documentation and Registry publication.

## Gates

- [x] Scope and license confirmed.
- [x] Isolated ComfyRemote feature worktree.
- [x] Private plugin repository created and initial source committed.
- [x] Isolated ComfyUI test environment starts with required sample nodes.
- [x] Pairing, revocation, reconnect and strict command boundaries tested.
- [x] Duplicate prompt submission is prevented after lost responses or restart.
- [x] Workflow import creates idempotent drafts and never publishes automatically.
- [x] Owner UI and ComfyUI sidebar verified in a real browser.
- [x] Staging image and video workflows complete and outputs can be downloaded.
- [x] Audio and mixed-media transport/serialization tests pass.
- [x] Staging self-use release installed and rollback recorded.
- [ ] Publisher ID reserved; documentation, screenshots and privacy notes complete.
- [ ] Public release and Registry publication verified.

## Deferred

Multi-device routing, automatic model installation, workflow library background
sync, complete in-plugin field editing and automatic publishing are out of scope.

## Protocol v1

The connector uses outbound HTTPS. The server authenticates each request with a
revocable device token. Pairing codes expire after fifteen minutes and are single use.
The server hands out commands at most once; the device journals command receipts
before local execution. Uncertain prompt submissions are not automatically retried.
Media is transferred in bounded chunks so large videos do not depend on a single
large Cloudflare request. Idle polls and command state use local SQLite, not D1.
The command surface exposes only the ComfyUI operations required to run jobs.
It provides no shell, node installer or general file-read endpoint. Installed
custom nodes retain their own process permissions; this is not a node sandbox.
