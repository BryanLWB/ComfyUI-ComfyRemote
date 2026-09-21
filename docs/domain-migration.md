# Controlled project domain migration (0.2.8)

The default hosted service is https://app.comfy-remote.com. Custom self-hosted URLs remain supported.

At startup, the connector may migrate an approved legacy project origin to its fixed replacement only after the target verifies the existing device and instance, explicitly declares that old origin, and reports a maintenance/idle state. Pending local executions or transfers prevent migration. Redirects and arbitrary targets are never accepted. Unavailable targets retain the old endpoint.

The device credential is retained. A DPAPI-protected journal resumes interrupted pairing writes. Thumbnail retries retain their IDs, attempts and schedule. Workflow association scope remains anchored to the original origin, preserving all ComfyUI users without reversing hashed scope keys or changing idempotent send payloads. The anchor is local bookkeeping, not a request destination.

The hosted server supplies this attestation during the coordinated cutover. Legacy self-hosted servers that do not supply device identity and idle attestation are not automatically migrated; operator configuration migration is required without changing installed service binaries. Never unpair as a substitute for origin migration.

After all devices and new URLs pass acceptance, operators can retire the old entry points. Do not publish a new plugin package until the new server can attest migration and the exact package has passed the isolated checks.
