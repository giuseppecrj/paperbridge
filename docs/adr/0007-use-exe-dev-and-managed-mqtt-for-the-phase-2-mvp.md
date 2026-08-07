# ADR 0007: Use exe.dev and managed MQTT for the Phase 2 MVP

- Status: Accepted
- Date: 2026-08-07
- Supersedes: ADR 0006

## Context

ADR 0006 selected a Mac mini, local Mosquitto, and optional Tailscale Serve for
the private Phase 2 MVP. That choice minimized infrastructure before the product
loop and device network path were proven.

The private REST/MCP/MQTT product loop, Wi-Fi control plane, and direct W5500
printer path are now implemented and physically verified on the purchased
hardware. A bounded EMQX Serverless spike also physically verified MQTT/TLS CA
and SNI validation, automatic clock synchronization, bounded message handling,
and concurrent W5500 printer reachability. The remaining uncertainty is cloud
operation, not whether MicroPython can establish the selected managed-broker
path. See `docs/emqx-tls-spike.md` for the exact evidence boundary.

exe.dev provides a persistent Linux VM and a private HTTPS proxy suitable for
the existing long-running Node service. It cannot expose an ordinary public
MQTT TCP listener, so the Host and Device need a managed broker they can both
reach.

## Decision

Deploy the private Phase 2 application service on one separate exe.dev
production VM and use EMQX Serverless for deployed MQTT/TLS. Preserve the
existing application, protocol, device, rendering, and delivery contracts.
EMQX remains replaceable: runtime job traffic uses standard MQTT 3.1.1, QoS 1,
non-retained messages, and versioned Paperbridge topics. Provider rules,
webhooks, registries, and job systems are not part of this slice.

Local Mosquitto and plaintext MQTT remain the repeatable development and
integration-test path. Development may use disposable clones of the existing
`dotfiles` devbox. Production must not use or clone that devbox and must not
contain personal AI credentials, signing keys, or SSH-agent forwarding.

### Private HTTP boundary

The Node service binds to loopback behind exe.dev's private HTTPS proxy. One
Owner and Sender access one configured Physical Inbox with a finite-expiry,
VM-scoped exe.dev credential sent in `X-Exedev-Authorization`. This credential
protects infrastructure access; it is not a Paperbridge Invite or sender
authorization model. Public sharing, application OAuth, accounts, pairing,
Invites, and multi-device routing remain out of scope.

Permit only configured exe.dev and loopback Host values. Permit requests without
an Origin for non-browser MCP clients. When Origin is present, permit only the
configured HTTPS exe.dev origin and explicit loopback development origins.

`/health` reports process liveness. `/ready` reports application MQTT
connectivity and returns unavailable while MQTT is disconnected. Neither route
claims that a Device or Printer is reachable.

### VM operation

Run the current Node entry point directly under one hardened systemd service as
a dedicated non-login `paperbridge` user. Use no Linux capabilities, no new
privileges, private temporary storage, protected home directories, and read-only
system paths. Store runtime secrets outside the repository in a root-owned
`0600` systemd environment file. Log structured application output to journald.

Attach a repository-scoped, read-only exe.dev GitHub integration directly to the
production VM. Deploy an exact reviewed commit through a checked-in `just` and
SSH operator workflow. Install locked dependencies, restart the service, verify
health and readiness, and retain the prior commit as the explicit rollback
target. Initial deployment remains manual. GitHub-hosted deployment becomes
appropriate when deployment frequency or another release owner justifies an
expiring CI credential, protected GitHub environment, concurrency control, and
explicit rollback. A self-hosted Actions runner is not justified for one Owner.

exe.dev's `new --env` option is not the runtime secret mechanism because its
storage, restart lifetime, and service visibility are not documented. Token
replacement is manual before finite expiry; automated credential rotation is
deferred and must remain an explicit operating limitation.

### Delivery and acceptance

Cloud deployment does not change delivery semantics. Jobs remain online-only,
non-retained, and without automatic retry. Duplicate suppression remains bounded
to one Device boot. A timeout remains an Unknown Delivery Result and does not
permit automatic resubmission. Durable delivery is separate product work.

Implementation proceeds as three dependent slices:

1. application readiness and exe.dev Host/Origin policy;
2. private exe.dev deployment, supervision, secrets, and EMQX connectivity; and
3. cloud end-to-end physical acceptance.

Service restart and VM reboot acceptance use no-output checks first. Final
acceptance sends one authorized rich semantic job through private MCP, exe.dev,
EMQX, the Device, and the Printer. The correlated result may report
`delivered_to_printer`; an operator separately records the observed paper and
explicit cut.

## Considered options

- **Mac mini and local Mosquitto:** superseded because the managed MQTT/TLS
  device path is now physically credible and exe.dev is the selected persistent
  Host.
- **Docker:** viable but deferred. A dedicated VM and hardened systemd service
  provide the needed isolation with fewer moving parts. Reconsider Docker when
  multiple independently versioned services, promoted image releases, multiple
  release owners, a container-only target, or measured VM drift require an
  immutable image and image-based rollback.
- **GitHub Actions deployment:** viable but deferred. exe.dev has no documented
  GitHub OIDC federation or official deployment Action, so CI needs another
  expiring deployment credential.
- **Provider-specific EMQX behavior:** deferred unless a concrete acceptance
  criterion cannot be met simply with standard MQTT and the coupling remains
  outside Paperbridge contracts.

## Consequences

Phase 2 now depends on internet reachability, exe.dev private proxy
availability, and managed MQTT availability. The deployment adds manual VM
secret and token rotation. It does not add public availability, durable jobs,
production sender authorization, automatic rollback, metrics infrastructure, or
long-duration reliability evidence.

The research behind this decision is recorded in:

- `docs/research/cloud-compute-api-runtime-2026-08-07.md`;
- `docs/research/managed-mqtt-scout-2026-08-07.md`;
- `docs/research/exedev-mcp-auth-2026-08-07.md`;
- `docs/research/exedev-ci-env-deployment-2026-08-07.md`; and
- `docs/research/exedev-docker-deployment-2026-08-07.md`.
