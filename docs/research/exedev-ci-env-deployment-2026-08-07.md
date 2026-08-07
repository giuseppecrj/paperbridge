# exe.dev deployment and environment research

**Research date:** 2026-08-07  
**Scope:** One persistent Paperbridge Node service on one exe.dev VM. This is
research only. It is not a deployment or a hardware test.

## `--env` is a VM-create option, not a service environment API

The exe.dev agent skill directs agents to the documentation index. The current
CLI reference documents `--env KEY=VALUE` only as a repeatable option of
`ssh exe.dev new`; it gives an example with two variables. Its documented
purpose is **VM creation**. It is not documented for an arbitrary command, an
agent session, or a running service. [exe-skill] [exe-new]

**Undocumented gap:** Current primary documentation does not state if
`new --env` writes values to disk, injects them only at boot, exposes them to
later SSH sessions, or preserves them after VM restart. exe.dev documents
persistent VM disks, but that does not define the lifetime or storage location
of `--env` values. Do not put Paperbridge secrets in this flag until exe.dev
documents these details. [exe-overview]

This differs from exe.dev **integrations**. An integration stores its secret
server-side and injects it at the network edge. The VM can use, but cannot read,
that secret. This is documented for integration hostnames, not as a generic
process environment or systemd secret store. [exe-integrations]

## The documented GitHub integration is VM-to-GitHub access

exe.dev provides a GitHub App integration for private repository access without
GitHub tokens on the VM. A per-repository integration lets the **VM** clone
through `github.int.exe.xyz`; it can be read-only and supports `gh`.
[exe-github]

This is not a documented GitHub-hosted Actions deployment feature. Current
exe.dev documentation instead documents:

1. SSH as the programmatic API, including `ssh exe.dev ...` commands.
   [exe-api]
2. A GitHub Actions **self-hosted runner on an exe.dev VM**, registered from
   GitHub and kept alive with systemd. [exe-runner]

**Undocumented gap:** No current exe.dev primary source found describes an
official GitHub-hosted Action, webhook, or GitHub App event that deploys to an
exe.dev VM. Do not represent repository cloning as such a deployment
integration.

## No documented GitHub OIDC federation to exe.dev

GitHub OIDC removes a long-lived GitHub secret only when the target cloud
provider trusts GitHub's OIDC identity and exchanges the job JWT for an access
token. [github-oidc]

exe.dev documents SSH-key authentication and bearer tokens. Its HTTPS API can
issue a token through an authenticated SSH command, or create one locally by
signing with an exe.dev-account SSH private key. It recommends an expiry and
says there is no built-in replay nonce. [exe-https-api] [exe-local-key]

**Answer:** A GitHub-hosted workflow cannot use a documented OIDC federation
to authenticate to exe.dev. The documented non-interactive alternatives need a
credential already accepted by exe.dev: an SSH private key for SSH or local
token signing, or a pre-created exe.dev bearer token. A short-lived,
least-privilege bearer token in a protected GitHub environment secret avoids
an SSH private key, but it remains a bootstrap secret until rotation.
[github-secrets] Do not claim OIDC support without an exe.dev trust-
configuration source.

## Bounded options

### 1. Checked-in `just`/SSH deployment by the owner

- **Secrets:** Keep runtime MQTT credentials in a VM-local root-owned or
  service-user-readable environment file. The owner uses normal SSH. No GitHub
  deployment credential exists. Paperbridge already requires MQTT values and
  defaults the API bind to `127.0.0.1`. [paperbridge-server]
  [paperbridge-security]
- **Restart and failure:** One systemd unit runs
  `bun run --filter @paperbridge/api start` and restarts on failure. Serialize
  deployments through the one owner. Deploy a known commit, restart, and inspect
  service status. If it fails, reset to the prior commit and restart. Atomic
  releases and automatic rollback are not present or necessary for this MVP.
- **Burden:** This has the smallest trust boundary and operating surface. It
  needs the owner to deploy and verify.

### 2. GitHub-hosted Action deployment over exe.dev

- **Secrets:** Store an exe.dev SSH key or a limited, expiring exe.dev bearer
  token in a protected GitHub environment secret. Documented GitHub OIDC cannot
  replace it.
- **Restart and failure:** Use one GitHub workflow concurrency group for the
  VM. The workflow must restart systemd and test the service. Failed restart
  recovery needs an explicit rollback command; exe.dev does not supply it.
- **Burden:** This adds CI secret management, workflow review, and remote
  failure diagnosis. It is valid later, but is not the smallest safe path now.

### 3. Self-hosted Actions runner on the exe.dev VM

- **Secrets:** No inbound deployment SSH credential is needed because the job
  runs on the VM. However, workflow code runs near the service and its secrets.
  GitHub says self-hosted runners need not start clean for every job. Restrict
  the runner to this private repository. [github-runner]
- **Restart and failure:** exe.dev's guide uses a runner systemd unit with
  `Restart=always`; the application still needs its own systemd unit. Use one
  workflow concurrency group because jobs share the VM and checkout. Rollback
  remains explicit.
- **Burden:** This has the highest persistent-host exposure and maintenance:
  runner registration, updates, job cleanup, and workflow-code trust. It is not
  justified for one owner.

## Recommendation

Use **checked-in manual `just`/SSH deployment plus one systemd service** for
Phase 2. Keep the runtime environment file only on the VM, outside Git, with
least read access. Pin and install the existing locked dependencies, deploy one
reviewed commit, then restart and inspect the service. Do not use `new --env`
for secrets because its storage and lifetime are undocumented.

Move to GitHub-hosted CI/CD when deployments are frequent enough that manual
deploys cause missed or unreviewed releases, or when another owner needs
repeatable release authority. Then use a protected GitHub environment, an
expiring least-privilege exe.dev bearer token, one deployment-concurrency group,
explicit post-restart verification, and explicit rollback. Choose a self-hosted
runner only if CI needs VM-local network access. Isolate it from public or
untrusted workflow input.

**Not covered:** Public exposure, sender authorization, MQTT/TLS, device
provisioning, and hardware verification. The current Paperbridge service is
private and localhost-bound by default. [paperbridge-security]

[exe-skill]: https://exe.dev/docs/agent-skill
[exe-new]: https://exe.dev/docs/cli-new
[exe-overview]: https://exe.dev/docs/what-is-exe
[exe-integrations]: https://exe.dev/docs/integrations
[exe-github]: https://exe.dev/docs/integrations-github
[exe-api]: https://exe.dev/docs/api
[exe-runner]: https://exe.dev/docs/use-case-gh-action-runner
[github-oidc]: https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-cloud-providers
[github-secrets]: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
[github-runner]: https://docs.github.com/en/actions/concepts/runners/self-hosted-runners
[exe-https-api]: https://exe.dev/docs/https-api
[exe-local-key]: https://exe.dev/docs/https-api-local-key
[paperbridge-server]: ../../apps/api/src/server.ts
[paperbridge-security]: ../security.md
