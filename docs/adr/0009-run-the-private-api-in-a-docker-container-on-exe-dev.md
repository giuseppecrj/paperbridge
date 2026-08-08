# ADR 0009: Run the private API in a Docker container on exe.dev

- Status: Accepted; implementation staged.
- Date: 2026-08-07
- Amends: ADR 0007 VM operation

## Context

ADR 0007 selected a direct Node process under systemd for the private API and
explicitly deferred Docker. The API now needs an immutable image artifact,
digest-based rollback, and a repeatable path to a separate exe.dev API runtime
VM. This changes the API runtime packaging only. It does not change private
proxy access, MQTT/TLS, the Device, the Printer, semantic job contracts, or
honest delivery results.

This is a target design, not a claim that the container deployment has been
performed or accepted. The existing API route remains unchanged until the new
VM passes the stated no-output gates and an Owner explicitly approves route
cutover.

## Decision

Run one private API container on a new `exeuntu` exe.dev VM. systemd owns its
lifecycle; Docker has no competing restart policy. The container publishes only
`127.0.0.1:3000` on the VM, while the API listens on its container interface.
The exe.dev HTTPS proxy remains private and is the sole HTTP ingress.

Build each API image on the VM from an exact reviewed commit. Bun bundles the
TypeScript application for the Node target into `dist/server.js`; Node runs that
bundle. `sharp` remains external to the bundle so its Linux native binary loads
normally. Use a pinned Debian-based Node image. Deploy and roll back by image
digest, retaining the current and previous images locally. Bun remains workspace
and build tooling; it is not the production runtime.

Run the container as a non-root user with a read-only root filesystem, no Linux
capabilities, `no-new-privileges`, no Docker socket, and no host networking. Do
not add Docker Compose, a registry, a logging vendor, automatic image updates,
or guessed resource limits for this one-container service.

Keep non-secret deployment configuration versioned and separate from the
image. Fnox and 1Password remain on the deployment operator's machine. They
provide the MQTT password once through SSH stdin for systemd to encrypt.
systemd decrypts the credential at service start and Docker bind-mounts it
read-only at `/run/secrets/mqtt-password`. The API reads
`PAPERBRIDGE_MQTT_PASSWORD_FILE`; it must not receive that password through a
Docker environment variable. If the new VM cannot use encrypted systemd
credentials, setup stops for an explicit follow-up decision rather than silently
using persistent plaintext storage.

On deploy, the API enters a draining state, rejects new semantic submissions,
and waits up to the existing 15-second result timeout for in-flight work.
systemd allows 20 seconds for shutdown. This creates no retry, queue, or new
job lifecycle.

Implement and accept the change in stages:

1. On a feature branch, build and test the exact Node bundle locally against the
   existing simulator and host checks.
2. Bootstrap a new private exe.dev VM and validate the container, secret mount,
   private proxy, `/health`, `/ready`, and correlated no-output MQTT probe.
3. Rebuild from the exact merged commit and repeat no-output acceptance on the
   new VM.
4. In an explicit short maintenance window, move the custom-domain DNS and
   exe.dev domain registration to the accepted VM. If checks fail, explicitly
   restore the previous route and image digest.

The first stage keeps the existing single MQTT credential. Separate API and
Device MQTT principals with topic ACLs are deferred: they require managed-broker
policy and Device provisioning work and do not block Docker deployment.

## Considered options

- **Direct Node under systemd:** ADR 0007's original choice. It remains simpler,
  but image-digest deployment and rollback are now explicit requirements.
- **Bun runtime:** rejected. The current Node HTTP and MCP adapter path is
  Node-specific; Bun returned incorrect empty `200` responses for asynchronous
  API handlers in local no-output probes. Bun remains the build tool only.
- **Doppler, Vault, or Fnox at runtime:** rejected for this one VM. They add a
  runtime provider and bootstrap credential. Fnox is provisioning-only;
  systemd credentials deliver the runtime secret.
- **Docker Compose or a containerized broker:** rejected. The API is one
  container and deployed MQTT remains external.

## Consequences

The VM must run and receive security updates for Docker and the pinned base
image. Image builds must verify the selected VM architecture and `sharp` native
loading. Deployment and routine API-password rotation remain manual operator
work. The no-output checks prove API and MQTT-client operation only; they do
not prove Device reachability, Printer delivery, or paper output.

As of 2026-08-08, the digest-pinned image and hardened local container acceptance
are implemented and Host-tested on Linux ARM64 under OrbStack. This does not
prove the future exe.dev VM architecture, deployment, private proxy, or route.

The research behind this decision is recorded in:

- `docs/research/exedev-docker-deployment-2026-08-07.md`;
- `docs/research/exedev-ci-env-deployment-2026-08-07.md`;
- `docs/research/fnox-secrets-workflow.md`; and
- `docs/research/node-vs-bun-api-runtime-2026-08-07.md`.
