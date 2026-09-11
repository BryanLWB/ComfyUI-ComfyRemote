# Manager installation verification

Verified on 2026-09-11 in an isolated Windows ComfyUI installation, with a separate
user directory and local synthetic hosted account. Production pairing and canvas
were not modified.

| Check | Result |
| --- | --- |
| ComfyUI / frontend / Python | 0.34.5 / 1.49.6 / 3.13.12 |
| Search `ComfyRemote` | Found publisher `bryan711` |
| Search card initial version | `nightly` |
| Open version menu | `0.2.0` offered |
| Select `0.2.0`, click Install | Registry ZIP downloaded and extracted; dependency step completed |
| Installed version | `0.2.0` |
| Apply changes | Backend restarted and plugin imported successfully |
| Refresh browser | ComfyRemote sidebar loaded |
| Pair to local hosted service | Connected with persisted Windows-protected credentials |
| Send isolated workflow through installed plugin | Import succeeded without changing canvas or running generation |

The release source remains `741b927d57463c4d5ab0ba6df25807fa49ab66f7`.
No new package version was published and the existing release was not overwritten.
This check uses the Manager's offered version selector, not a forced installation
or a change to Manager security settings.

The Registry API still reports `NodeVersionStatusFlagged` for version `0.2.0`
(version ID `99725566-3201-4fb8-896d-4feab6cd3b77`). Its public API does not provide
a diagnostic reason. Node visibility, version review status and successful
installation are separate observations. An active node or a `nightly` label alone
cannot establish whether a fixed release can be installed.

Pending: clarification of the Flagged reason and default latest-version listing
from Registry; installation on other Manager versions and a clean Windows system.
No external support message has been sent. No nightly installation was substituted
for this fixed-version verification.
