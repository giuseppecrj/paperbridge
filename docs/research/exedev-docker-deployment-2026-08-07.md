# exe.dev Docker deployment research

**Research date:** 2026-08-07  
**Scope:** Packaging one private Paperbridge Node service on one separate
exe.dev production VM. This is research, not an accepted deployment decision.

## Question

Would Docker add useful security and operating control compared with a direct,
hardened systemd service?

Docker does not replace SSH in the selected deployment model. The Owner still
uses SSH to update the production VM. Docker changes how the VM packages and
runs the application after deployment.

## Security

Docker containers share the host kernel. Docker documents namespaces,
capabilities, seccomp, and daemon access as separate security controls; a
default container is not the same isolation boundary as a VM. Membership in the
`docker` group grants root-level privileges. [docker-security]
[docker-daemon]

A hardened container can reduce application access with a non-root user, a
read-only filesystem, dropped capabilities, `no-new-privileges`, and a seccomp
profile. These controls are not automatic. The official Node image guidance
also recommends running as a non-root user. [docker-node]

A direct systemd service can apply similar process restrictions without a
container daemon. Relevant controls include `NoNewPrivileges=`,
`ProtectSystem=`, `ProtectHome=`, `PrivateTmp=`, and an empty capability set.
[systemd-exec]

Paperbridge already uses a separate production VM and one trusted application.
It does not run sender-supplied code. Docker therefore adds defense in depth,
but it does not create a new hard isolation boundary for the current threat
model.

## Reproducibility and rollback

Docker's strongest benefit is a versioned image. A multi-stage build can pin the
Node base image by digest and produce the same application filesystem on each
deployment. Keeping a previous digest gives a fast rollback target.
[docker-multistage]

The direct alternative pins Node, Bun, and dependencies with `mise.toml`,
`bun.lock`, and the repository checkout. It does not freeze the VM operating
system and CA packages. Rollback checks out the previous reviewed commit,
installs its locked dependencies, and restarts the service.

A Dockerfile also becomes another runtime-version source that must stay aligned
with `mise.toml`. Image updates must rebuild and retest both application and
base-image changes. A registry is optional when the image is built on the VM,
but remote CI or digest promotion would normally add one.

## Secrets

Docker does not remove the need for a VM-local secret source. Values passed as
container environment variables can appear in container inspection output.
Docker Compose supports file-backed secrets, but Paperbridge currently expects
most MQTT credentials as environment variables. [docker-secrets]

A root-owned `0600` systemd environment file protects values at rest from other
unprivileged VM users. The application still receives those values in its
process environment. Neither design protects a secret from the application or
host root.

The exe.dev `new --env` option is not a documented persistent service-secret
store. See `docs/research/exedev-ci-env-deployment-2026-08-07.md`.

## Networking

The direct service binds to `127.0.0.1`, and exe.dev's private HTTPS proxy
forwards to that port.

A bridged container must listen on its container interface and publish with an
explicit host-loopback binding such as `127.0.0.1:3000:3000`. Omitting the host
address can publish on all host interfaces. This makes an external-reachability
acceptance check mandatory. [docker-publish]

Host networking would preserve the application's loopback bind, but it removes
Docker network isolation. The bridged, loopback-published form is preferable if
Docker is selected.

## Operating cost

Runtime CPU and memory overhead for one container are not the main concern. The
additional operating surface is:

- the Docker daemon and its patching;
- a Dockerfile and `.dockerignore`;
- base-image pinning and rebuild policy;
- container hardening flags;
- image retention or registry policy; and
- prevention of accidental non-loopback port publication.

systemd remains useful in either design. It can run the Node process directly,
or supervise the exact container invocation. Docker restart policies are also
available, but two independent restart policies should not compete.

## Corrected architecture assumption

Do not assume that every exe.dev VM is ARM64. Current exe.dev documentation
shows ordinary Linux VMs but does not promise one architecture for every VM.
Inspect the selected production VM and build the image for that architecture.
The `sharp` dependency supports common Linux architectures, but the production
image must prove that its native binary loads. [exe-overview] [sharp-install]

## Recommendation

For this one-Owner, one-service Phase 2 deployment, use a dedicated service user
and a hardened direct systemd unit. It gives the relevant process restrictions
without adding a container daemon or a second runtime-version source. Keep the
production VM separate from the dotfiles devbox and its clones.

Docker is also viable. Select it now only if image reproducibility and fast
image rollback are explicit Phase 2 requirements. If selected, use one hardened
container under systemd, not Compose for its own sake. Require a non-root user,
read-only root filesystem, no capabilities, `no-new-privileges`, explicit
loopback port publication, a pinned base digest, and a clean secret strategy.

Reconsider Docker when one of these triggers occurs:

1. Paperbridge deploys multiple independently versioned services.
2. Releases need promoted image digests or fast image rollback.
3. More release owners need one immutable deployment artifact.
4. The target platform requires a container image.
5. VM environment drift causes a measured failure.

## Acceptance checks for either choice

- The process restarts after service failure and VM reboot.
- The application port is unreachable except through the private exe.dev proxy.
- The process runs without root privileges or Linux capabilities.
- The runtime cannot write outside explicitly allowed paths.
- Runtime secrets are absent from Git, logs, command arguments, and build
  layers.
- The selected `sharp` native binary loads on the production architecture.
- A failed deployment can return to the prior reviewed version.

[docker-security]: https://docs.docker.com/engine/security/
[docker-daemon]: https://docs.docker.com/engine/security/#docker-daemon-attack-surface
[docker-node]: https://github.com/nodejs/docker-node/blob/main/docs/BestPractices.md
[docker-multistage]: https://docs.docker.com/build/building/multi-stage/
[docker-secrets]: https://docs.docker.com/compose/how-tos/use-secrets/
[docker-publish]: https://docs.docker.com/engine/network/port-publishing/
[systemd-exec]: https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html
[exe-overview]: https://exe.dev/docs/what-is-exe
[sharp-install]: https://sharp.pixelplumbing.com/install/
