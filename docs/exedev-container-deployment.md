# exe.dev candidate container operator

This runbook describes the checked-in workflow for one hardened Paperbridge API
container on a separate `exeuntu` VM. The workflow is Host-tested through dry
runs and fake remote commands. Real-VM acceptance is tracked separately in
issue #29 and must not be inferred from this runbook.

The current `paperbridge-prod` VM and `api.paperbridge.tech` route remain
unchanged. The operator rejects `paperbridge-prod`. The existing direct-Node
production runbook remains in [`exedev-deployment.md`](exedev-deployment.md)
until explicit cutover.

## Boundaries

- Every command must name the new VM through `EXEDEV_VM`; there is no default.
- Every mutating command also requires `EXEDEV_CONFIRM_VM` to exactly match that
  VM name. Set it for one command instead of keeping it in `.env`.
- SSH uses batch mode, disables agent forwarding, and sends no secret in an
  argument.
- Fnox and 1Password run only on the operator machine.
- Bootstrap requires the exe.dev marker, rejects legacy Paperbridge deployment
  paths, and stops if encrypted systemd credentials do not work.
- The VM builds an exact 40-character commit and records the resulting local
  Docker image ID as an immutable `sha256:` digest.
- systemd is the only restart authority. Docker receives no restart policy.
- Verification uses loopback health/readiness and the no-output MQTT tracer. It
  does not submit a Semantic Print Job or contact the Printer.
- This workflow has no proxy-visibility, custom-domain, DNS, Device, Printer,
  feed, cut, firmware, or physical-output command.

## Owner checkpoints

Do not combine these checkpoints into an unattended script.

- **Create VM:** Creates a separate billed VM and attaches repository access.
  The Owner approves the exact new VM name, `exeuntu` image, and read-only
  GitHub integration.
- **Bootstrap:** Installs Docker, enables its service, creates root-owned state,
  and clones the repository. The Owner approves the exact VM and reviewed
  commit.
- **Provision credential:** Sends the production MQTT password through SSH
  stdin and writes an encrypted blob on the VM. The Owner unlocks 1Password,
  inspects the target name, and approves.
- **Build:** Fetches one exact commit and builds an image on the VM. The Owner
  approves the commit and records the returned digest and architecture.
- **Deploy:** Changes the candidate VM service to one exact digest. The Owner
  approves the digest and recorded rollback digest.
- **Probe:** Sends one correlated MQTT tracer request and no Semantic Print Job.
  The Owner confirms that no-output broker/Device contact is allowed.
- **Restart or reboot:** Interrupts the candidate API runtime. The Owner
  approves the exact candidate VM and repeats no-output checks afterward.
- **Rotate credential:** Replaces the encrypted MQTT credential and restarts the
  candidate service. The Owner approves the new 1Password value and rollback
  plan.
- **Rollback:** Switches the candidate service to its recorded previous digest.
  The Owner approves both current and previous digests.
- **Proxy acceptance:** Changes or verifies the new VM's private exe.dev
  ingress. **Stop here. Issue #29 requires separate Owner authorization.**
- **DNS or custom-domain cutover:** Moves `api.paperbridge.tech` or exe.dev
  domain registration. **This runbook forbids that action. Issue #30 requires a
  maintenance window and separate Owner authorization.**

## 1. Create the candidate VM — Owner action

Choose a name that is not `paperbridge-prod`. Select the configured read-only
GitHub integration for `giuseppecrj/paperbridge`. Review the command before
running it:

```sh
export EXEDEV_VM=<new-vm-name>
export EXEDEV_GITHUB_INTEGRATION=<read-only-integration-name>
ssh -o BatchMode=yes -o ForwardAgent=no exe.dev new \
  --name "$EXEDEV_VM" \
  --image exeuntu \
  --integration "$EXEDEV_GITHUB_INTEGRATION"
```

Do not pass secrets through `new --env`, a setup script, or forwarded SSH
credentials. Record the returned VM name. Do not configure the proxy or custom
domain in this issue.

Before the first direct connection, scan only the published RSA host-key type
and require exactly one key with exe.dev's [published fingerprint][exe-dev-host-key]:

```sh
candidate_host="$EXEDEV_VM.exe.xyz"
candidate_key=$(mktemp)
expected_fingerprint='SHA256:JJOP/lwiBGOMilfONPWZCXUrfK154cnJFXcqlsi6lPo'
trap 'rm -f "$candidate_key"' EXIT
ssh-keyscan -T 10 -t rsa "$candidate_host" >"$candidate_key"
test "$(wc -l <"$candidate_key" | tr -d ' ')" = 1
candidate_fingerprint=$(ssh-keygen -lf "$candidate_key" | awk '{print $2}')
printf 'candidate_fingerprint=%s\n' "$candidate_fingerprint"
test "$candidate_fingerprint" = "$expected_fingerprint"
```

Only after that exact programmatic comparison, enroll the verified key:

```sh
install -d -m 0700 "$HOME/.ssh"
touch "$HOME/.ssh/known_hosts"
chmod 0600 "$HOME/.ssh/known_hosts"
ssh-keygen -R "$candidate_host"
cat "$candidate_key" >>"$HOME/.ssh/known_hosts"
rm -f "$candidate_key"
trap - EXIT
```

Do not enroll a different fingerprint. The operator forces
`StrictHostKeyChecking=yes` on every subsequent SSH connection.

[exe-dev-host-key]: https://exe.dev/docs/faq/host-key.md

## 2. Bootstrap Docker and encrypted credentials — Owner action

Use the exact reviewed commit that contains the operator workflow:

```sh
export PAPERBRIDGE_SHA=<40-character-reviewed-commit>
EXEDEV_CONFIRM_VM="$EXEDEV_VM" just exedev-container-bootstrap
```

Bootstrap performs a read-only preflight before it uploads the remote helper. It
then:

1. requires the `/exe.dev` marker and no legacy Paperbridge service;
2. installs `ca-certificates`, curl, Git, and the Ubuntu `docker.io` package;
3. enables Docker and requires `docker info` to succeed;
4. runs an encrypted `systemd-creds` round trip through a transient systemd
   unit without printing the probe value;
5. clones through the read-only exe.dev GitHub integration and fetches the exact
   commit; and
6. writes a non-secret bootstrap marker only after every gate passes.

If encrypted credentials are unavailable, bootstrap stops. There is no
plaintext environment-file fallback.

## 3. Provision the MQTT credential — Owner action

First verify the production Fnox reference without printing its value:

```sh
just production-secrets-check
```

Then approve the exact candidate VM and provision the encrypted blob:

```sh
EXEDEV_CONFIRM_VM="$EXEDEV_VM" just exedev-container-credential
```

Fnox resolves `PAPERBRIDGE_MQTT_PASSWORD` on the operator machine. The operator
captures and removes that environment variable before it starts SSH, then sends
the bytes through SSH stdin. The remote helper pipes stdin directly into
`systemd-creds encrypt --name=mqtt-password`. It validates the encrypted blob
through a transient systemd unit and atomically installs it at:

```text
/etc/credstore.encrypted/paperbridge-mqtt-password
```

The blob is root-owned mode `0600`. The plaintext value is not placed in Git, a
command argument, Docker metadata, systemd environment state, or the service
log.

## 4. Build the exact image — Owner action

```sh
EXEDEV_CONFIRM_VM="$EXEDEV_VM" \
PAPERBRIDGE_SHA=<40-character-reviewed-commit> \
  just exedev-container-build
```

The builder fetches only that commit, checks that the detached worktree is at
that commit, adds the revision label, and builds with the checked-in Dockerfile.
It reports values in this form:

```text
built_sha=<commit> image_digest=sha256:<64-hex> architecture=<vm-architecture>
```

Record all three non-secret values. A local Docker image ID is the immutable
selector for this no-registry workflow. Do not deploy the build tag. A rebuild
of the same commit can produce a different image ID, so always use the digest
reported by that build.

## 5. Deploy the recorded digest — Owner action

Provision the credential before the first deploy. Then set the exact recorded
digest:

```sh
export PAPERBRIDGE_IMAGE_DIGEST=sha256:<64-hex>
EXEDEV_CONFIRM_VM="$EXEDEV_VM" just exedev-container-deploy
```

Deploy verifies that this workflow built the digest, installs the unit and
non-secret environment from that build's exact commit, records the current and
previous digests, and restarts `paperbridge-container.service`. systemd requires
both loopback `/health` and `/ready` before activation succeeds. Only after that
bounded gate does deploy remove older release images. The current and
immediately previous images remain available.

The service:

- starts after `network-online.target` and `docker.service`;
- loads the encrypted MQTT credential with `LoadCredentialEncrypted=`;
- copies the decrypted value to a root-only `/run/paperbridge-container`
  directory because dockerd cannot reliably see a credential mount in another
  service mount namespace;
- bind-mounts that transient file read-only at
  `/run/secrets/mqtt-password`;
- removes the transient host file when the service stops;
- publishes only `127.0.0.1:3000:3000`;
- runs the non-root image with a read-only root filesystem, no capabilities,
  `no-new-privileges`, bridged networking, no Docker socket, and no Docker
  restart policy; and
- gives the API its existing 15-second result bound inside systemd's 20-second
  stop allowance.

If daemon reload, enable, or restart fails, the helper restores the prior unit,
non-secret environment, current digest, and previous digest, then attempts to
restart the prior image. It does not prune any image on that path. If recovery
restart also fails, the prior digest state remains recorded but the service can
remain down; inspect `status` and `logs` before another explicit action.

## 6. Observe and run no-output checks

These read-only actions require the explicit VM name but no confirmation token:

```sh
just exedev-container-status
just exedev-container-logs
just exedev-container-verify
```

`verify` calls only the candidate VM's host-loopback `/health` and `/ready`
endpoints. `/health` proves process liveness. `/ready` proves MQTT connectivity
and submission acceptance; it does not prove Device or Printer state.

The correlated MQTT tracer is an external no-output action and requires Owner
confirmation:

```sh
EXEDEV_CONFIRM_VM="$EXEDEV_VM" just exedev-container-probe
```

The probe runs `node dist/main.js` inside the active image. It uses the mounted
credential file and the existing tracer topics. It does not call `/api/jobs`,
the MCP print tool, or the Printer.

## 7. Restart and reboot verification — Owner actions

Service restart:

```sh
EXEDEV_CONFIRM_VM="$EXEDEV_VM" just exedev-container-restart
just exedev-container-status
just exedev-container-verify
EXEDEV_CONFIRM_VM="$EXEDEV_VM" just exedev-container-probe
```

VM reboot:

```sh
EXEDEV_CONFIRM_VM="$EXEDEV_VM" just exedev-container-reboot
# Wait until the exact VM accepts SSH again.
just exedev-container-status
just exedev-container-verify
EXEDEV_CONFIRM_VM="$EXEDEV_VM" just exedev-container-probe
```

Record that the same digest returned after restart and reboot. Running these
commands against a real VM is issue #29 acceptance, not evidence from #28.

## 8. Rotate the credential — Owner action

```sh
just production-secrets-check
EXEDEV_CONFIRM_VM="$EXEDEV_VM" just exedev-container-rotate
just exedev-container-verify
EXEDEV_CONFIRM_VM="$EXEDEV_VM" just exedev-container-probe
```

Rotation validates a new encrypted blob before replacing the old blob. If the
service restart fails, the helper restores the previous encrypted blob and
attempts to restart with it. No plaintext rollback file is created.

## 9. Roll back the image — Owner action

Inspect both digests first:

```sh
just exedev-container-status
```

Then approve the swap:

```sh
EXEDEV_CONFIRM_VM="$EXEDEV_VM" just exedev-container-rollback
just exedev-container-status
just exedev-container-verify
EXEDEV_CONFIRM_VM="$EXEDEV_VM" just exedev-container-probe
```

Rollback swaps current and previous immutable digests. It does not rebuild an
image or resolve a tag.

## Evidence boundary

For #28, record only checked-in code, dry-run output without secrets, focused
test results, and repository checks. Do not claim VM, proxy, MQTT, restart,
reboot, Device, Printer, or physical-output success.

Issue #29 may record the exact VM, commit, digest, architecture, tool versions,
private-proxy observations, health/readiness results, and correlated probe IDs
after separate Owner authorization. Issue #30 alone owns the merged-commit
rebuild, custom-domain registration, DNS change, maintenance window, and route
rollback.
