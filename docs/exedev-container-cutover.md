# exe.dev container production cutover

This runbook records the manual issue #30 promotion of the accepted container
VM to `api.paperbridge.tech`. The cutover completed on 2026-08-08. Do not rerun
its activation steps without a new approved maintenance window.

`paperbridge-api` is the active production VM. `paperbridge-prod` remains the
route rollback target, and the accepted previous container digest remains the
image rollback target. Issue #49 keeps both VMs and both image digests until the
Owner explicitly ends the rollback window.

## Fixed scope

```text
pre-cutover VM:    paperbridge-prod
active VM:         paperbridge-api
custom domain:     api.paperbridge.tech
rollback CNAME:    paperbridge-prod.exe.xyz
active CNAME:      paperbridge-api.exe.xyz
```

The custom domain and both exe.dev VM shares must remain private. Verification
uses GET `/health`, GET `/ready`, and the correlated no-output MQTT tracer only.
It does not submit a Semantic Print Job or contact the Printer.

## Stop conditions

Stop before each Owner checkpoint below. Do not continue if:

- the implementation source is not merged;
- the local checkout is dirty or its merged commit differs from `origin/main`;
- either VM, proxy, custom-domain registration, or CNAME differs from the fixed
  scope;
- production is not healthy and ready before the window;
- the candidate is not on the recorded current and previous digests;
- either share is public or has an unexpected link, user, team, or team access;
- the production rollback token or route information is unavailable;
- `EXEDEV_CONFIRM_ROUTE` does not exactly describe the approved old and new
  route;
- the candidate token has no explicit finite expiry or is not in an approved
  secret store; or
- any command would send printing work, operate the Device, or operate the
  Printer.

A failed gate after the window starts invokes the full route and image rollback.
Do not improvise a partial route.

## Owner checkpoints

The Owner approves these effects separately:

1. **Merged build:** exact merged commit and candidate VM build.
2. **Merged deploy:** exact new digest and recorded accepted rollback digest.
3. **Candidate probe:** one pre-cutover no-output broker/Device probe.
4. **Service restart:** restart only the candidate, require the same merged
   digest, and run one new no-output probe.
5. **VM reboot:** reboot only the candidate, require the same merged digest, and
   run one new no-output probe.
6. **Candidate token:** exact finite expiry, label, and secret-store target.
7. **DNS preparation:** Squarespace TTL reduction from the observed `1800` to
   `300`, followed by at least one old-TTL wait.
8. **Maintenance window:** exact old/new CNAME values, the guarded exe.dev route
   activation and restoration confirmations, and all rollback commands.
9. **Post-cutover probe:** one custom-route no-output broker/Device probe.
10. **Rollback, if needed:** restore the old CNAME/domain registration and the
    prior accepted candidate image, then verify both.
11. **End rollback window:** only after a separate Owner decision. This issue
    does not delete or stop the old VM.

Approval for one checkpoint is not approval for another.

## Prepare the merged release

Fetch `origin/main` only after the implementation stack is merged. Record the
exact 40-character commit and prove it is the remote main tip:

```sh
git fetch origin main
export PAPERBRIDGE_SHA=<40-character-merged-commit>
test "$(git rev-parse origin/main)" = "$PAPERBRIDGE_SHA"
test -z "$(git status --porcelain)"
```

Name the exact candidate on each operator command. Do not keep its confirmation
value in `.env` or treat it as approval for a later command.

Take the production and candidate baselines before any build:

```sh
just production-status
just production-verify
EXEDEV_VM=paperbridge-api just exedev-container-status
EXEDEV_VM=paperbridge-api just exedev-container-verify
```

Record the current custom-domain and private-share state without changing it:

```sh
control=(ssh -o BatchMode=yes -o ForwardAgent=no -o StrictHostKeyChecking=yes exe.dev)
"${control[@]}" domain ls -a --json
"${control[@]}" share show paperbridge-prod --json
"${control[@]}" share show paperbridge-api --json
dig @nsa1.squarespacedns.com api.paperbridge.tech CNAME +noall +answer
```

Expected pre-cutover route:

```text
api.paperbridge.tech CNAME paperbridge-prod.exe.xyz
api.paperbridge.tech -> paperbridge-prod
```

After the merged-build checkpoint, build the exact merged commit:

```sh
EXEDEV_VM=paperbridge-api \
EXEDEV_CONFIRM_VM=paperbridge-api \
PAPERBRIDGE_SHA=<40-character-merged-commit> \
  just exedev-container-build
```

Record the returned commit, architecture, and new immutable digest. Inspect its
revision label, runtime user, CA bundle, and image metadata before asking for
deploy approval.

After the merged-deploy checkpoint, deploy only that recorded digest:

```sh
EXEDEV_VM=paperbridge-api \
EXEDEV_CONFIRM_VM=paperbridge-api \
PAPERBRIDGE_IMAGE_DIGEST=sha256:<64-hex> \
  just exedev-container-deploy
```

The deploy result must record the issue #29 accepted digest as
`rollback_digest`. Verify loopback health/readiness, private proxy state,
container hardening, current/previous digest retention, and actual-secret
absence again. Then obtain separate approval for one pre-cutover probe:

```sh
EXEDEV_VM=paperbridge-api just exedev-container-verify
EXEDEV_VM=paperbridge-api \
EXEDEV_CONFIRM_VM=paperbridge-api \
  just exedev-container-probe
just production-verify
```

Stop if production changed or either check fails.

Repeat the recovery gates on the exact merged digest. Each restart/reboot and
probe pair needs its own checkpoint; one approval does not cover both.

Candidate service restart:

```sh
just production-verify
EXEDEV_VM=paperbridge-api \
EXEDEV_CONFIRM_VM=paperbridge-api \
  just exedev-container-restart
EXEDEV_VM=paperbridge-api just exedev-container-status
EXEDEV_VM=paperbridge-api just exedev-container-verify
EXEDEV_VM=paperbridge-api \
EXEDEV_CONFIRM_VM=paperbridge-api \
  just exedev-container-probe
just production-verify
```

Candidate VM reboot:

```sh
just production-verify
EXEDEV_VM=paperbridge-api \
EXEDEV_CONFIRM_VM=paperbridge-api \
  just exedev-container-reboot
# Wait until paperbridge-api.exe.xyz accepts SSH again.
EXEDEV_VM=paperbridge-api just exedev-container-status
EXEDEV_VM=paperbridge-api just exedev-container-verify
EXEDEV_VM=paperbridge-api \
EXEDEV_CONFIRM_VM=paperbridge-api \
  just exedev-container-probe
just production-verify
```

After each action, require the merged digest, healthy/ready candidate, healthy/
ready production, private proxy, and one new successful correlation ID. Stop and
restore the candidate image if a recovery gate fails before the route window.

## Prepare private client access

A token for `paperbridge-prod` does not authorize `paperbridge-api`. Before the
window, the Owner selects an explicit finite expiry and approved secret-store
location for a new VM-scoped token. Generate it only after that checkpoint:

```sh
token_file=$(mktemp)
chmod 0600 "$token_file"
trap 'rm -f "$token_file"' EXIT
ssh -o BatchMode=yes -o ForwardAgent=no -o StrictHostKeyChecking=yes \
  exe.dev ssh-key generate-api-key \
  --vm=paperbridge-api \
  --label=Paper-Bridge-MCP-v2 \
  --exp=<finite-expiry> \
  --json >"$token_file"
```

Move the token from that file to the approved secret store without showing it,
then remove the file and clear the trap. Do not print, paste, log, or commit the
token. Keep the old production token available for rollback. The edge header
shape is `X-Exedev-Authorization: Bearer <token>`.

Before DNS changes, verify that the new token reaches only the candidate GET
health/readiness routes through `https://paperbridge-api.exe.xyz`. Verify that
anonymous and invalid-token requests do not reach the service. Prepare the
approved private client to use the new token after cutover, but retain its old
production token separately for rollback.

## Prepare DNS before the window

The authoritative CNAME TTL was `1800` seconds during issue #30 discovery.
After separate DNS-preparation approval, use the Squarespace DNS dashboard to
change only the `api` CNAME TTL to `300`. Keep its target at
`paperbridge-prod.exe.xyz`.

Wait at least 1800 seconds before opening the maintenance window. Then require
the authoritative answer to show the old target and new TTL:

```sh
dig @nsa1.squarespacedns.com api.paperbridge.tech CNAME +noall +answer
```

Do not start the window if another record changed.

## Cut over during the approved window

Record the approved window, new merged digest, accepted rollback digest, old and
new CNAME values, domain commands, private-share commands, and full rollback
commands before execution. Ask approved Senders not to submit work during the
window. The old production service remains running as the route rollback target.

### 1. Change the CNAME

In the Squarespace DNS dashboard, change only:

```text
api  CNAME  paperbridge-prod.exe.xyz  ->  paperbridge-api.exe.xyz
TTL  300
```

Wait until the authoritative response is exactly the new target. Also check two
independent recursive resolvers:

```sh
dig @nsa1.squarespacedns.com api.paperbridge.tech CNAME +noall +answer
dig @1.1.1.1 api.paperbridge.tech CNAME +short
dig @8.8.8.8 api.paperbridge.tech CNAME +short
```

Stop and roll back if the authoritative answer is wrong or the bounded DNS wait
expires.

### 2. Move the exe.dev registration

Official exe.dev documentation requires DNS to point to the destination before
registration. Its documentation does not promise an atomic move between VMs.
The checked-in operator therefore requires the exact candidate CNAME, the exact
current registration on `paperbridge-prod`, private port `3000` on both shares,
no share grants, and this complete confirmation value before it mutates state:

```sh
EXEDEV_CONFIRM_ROUTE='paperbridge-prod:api.paperbridge.tech->paperbridge-api' \
  just exedev-container-route-activate
```

The operator removes only the verified old registration, adds only the expected
candidate registration, reasserts both private shares, and verifies the same DNS,
registration, and share state afterward. Expected output:

```text
route_vm=paperbridge-api
domain=api.paperbridge.tech
cname=paperbridge-api.exe.xyz
private=true
```

Stop and roll back if the guarded operator refuses or any mutation fails.

### 3. Verify the custom route

Use the new candidate token from the approved secret store. Keep it out of curl
arguments by writing only the header to a mode-`0600` temporary curl config and
removing that file with a shell trap.

Load `PAPERBRIDGE_EXEDEV_VM_TOKEN` from the approved secret store into only the
current shell. Create a temporary curl config so the token does not enter curl's
arguments:

```sh
set -euo pipefail
custom_url=https://api.paperbridge.tech
curl_config=$(mktemp)
chmod 0600 "$curl_config"
trap 'rm -f "$curl_config"' EXIT
token=${PAPERBRIDGE_EXEDEV_VM_TOKEN:?candidate VM token is required}
unset PAPERBRIDGE_EXEDEV_VM_TOKEN
printf 'header = "X-Exedev-Authorization: Bearer %s"\n' "$token" >"$curl_config"
unset token

anonymous_code=$(curl --silent --show-error --max-time 15 \
  --output /dev/null --write-out '%{http_code}' "$custom_url/health")
test "$anonymous_code" = 307
invalid_code=$(curl --silent --show-error --max-time 15 \
  --output /dev/null --write-out '%{http_code}' \
  -H 'X-Exedev-Authorization: Bearer invalid-paperbridge-cutover-token' \
  "$custom_url/health")
test "$invalid_code" = 401
health=$(curl --fail --silent --show-error --max-time 15 \
  --config "$curl_config" "$custom_url/health")
ready=$(curl --fail --silent --show-error --max-time 15 \
  --config "$curl_config" "$custom_url/ready")
test "$health" = '{"status":"ok"}'
test "$ready" = '{"status":"ready"}'
rm -f "$curl_config"
trap - EXIT
```

Then require:

1. DNS and exe.dev identify `paperbridge-api` as the route;
2. the active candidate digest equals the merged digest; and
3. production rollback information remains intact.

After separate post-cutover probe approval, run one tracer probe and recheck the
custom route:

```sh
EXEDEV_VM=paperbridge-api \
EXEDEV_CONFIRM_VM=paperbridge-api \
  just exedev-container-probe
EXEDEV_VM=paperbridge-api just exedev-container-verify
```

Record the correlation ID and only non-secret observations. This is route/API/
MQTT readiness evidence, not Device, Printer, delivery, or physical-output
evidence.

## Roll back

Run this complete rollback after any failed cutover gate. Do not wait for a
second failure.

### 1. Restore DNS

In Squarespace, restore only:

```text
api  CNAME  paperbridge-api.exe.xyz  ->  paperbridge-prod.exe.xyz
TTL  300
```

Wait for the authoritative record to show `paperbridge-prod.exe.xyz`.

### 2. Restore the exe.dev registration

The restore operator requires the exact production CNAME, accepts only the
candidate registration or the missing registration left by an interrupted
activation, and requires both shares to have their expected private state. Run
it only with the separately approved reverse confirmation:

```sh
EXEDEV_CONFIRM_ROUTE='paperbridge-api:api.paperbridge.tech->paperbridge-prod' \
  just exedev-container-route-restore
```

Expected output:

```text
route_vm=paperbridge-prod
domain=api.paperbridge.tech
cname=paperbridge-prod.exe.xyz
private=true
```

Use the retained old production token to verify custom-domain GET `/health` and
`/ready`. Verify anonymous and invalid-token denial again.

### 3. Restore the accepted candidate image

Inspect current and previous candidate digests. The previous value must be the
exact issue #29 accepted digest recorded before the window. After separate
rollback approval:

```sh
EXEDEV_VM=paperbridge-api \
EXEDEV_CONFIRM_VM=paperbridge-api \
  just exedev-container-rollback
EXEDEV_VM=paperbridge-api just exedev-container-status
EXEDEV_VM=paperbridge-api just exedev-container-verify
just production-status
just production-verify
```

After separate no-output probe approval, run one probe against each restored
runtime only if required by the approved rollback checklist. Keep the merged
candidate digest as the new previous value; do not prune it manually.

## Close the window

After successful cutover, keep all of these until the Owner explicitly ends the
rollback window:

- `paperbridge-prod` VM and its direct-Node service;
- old production token and non-secret route record;
- new `paperbridge-api` VM;
- merged current candidate digest;
- issue #29 accepted rollback digest; and
- DNS/domain rollback commands above.

Restore the DNS TTL only through a later approved DNS action. Do not stop,
remove, repurpose, or expose the old VM as part of #30 acceptance.

## Primary references

- [exe.dev custom domains](https://exe.dev/docs/cnames)
- [exe.dev domain CLI](https://exe.dev/docs/cli-domain)
- [exe.dev HTTPS tokens for VMs](https://exe.dev/docs/https-tokens-for-vms)
- [Squarespace DNS record editing](https://support.squarespace.com/hc/en-us/articles/360002101888-Adding-DNS-records-to-your-domain)
