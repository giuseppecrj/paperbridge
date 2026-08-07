# exe.dev private Host deployment

This is the manual Phase 2 workflow for one `paperbridge-prod` VM. It runs the
existing Node API as a hardened systemd service. It is not CI/CD, Docker, public
sharing, durable delivery, or physical acceptance.

## Boundaries

- The VM is a fresh exeuntu VM, not the `dotfiles` development base or a clone.
- Its only repository integration is read-only `giuseppecrj/paperbridge` access.
- The service binds `127.0.0.1:3000`. The exe.dev proxy is its only HTTP path,
  at `https://api.paperbridge.tech`.
- `/health` is process liveness. `/ready` is MQTT-client connectivity only.
- `production-probe` is a correlated no-output MQTT tracer probe. It does not
  submit a Semantic Print Job or contact the Printer.
- All checked-in SSH commands force `ForwardAgent=no`.

## Bootstrap and configuration

Run repository checks first. Use an exact reviewed commit SHA, never a branch:

```sh
PAPERBRIDGE_SHA=<40-character-sha> just production-bootstrap
just production-configure
just production-verify
just production-probe
```

`production-configure` uses the `host,emqx-spike` Fnox profiles. It base64
encodes the EMQX password directly into `/etc/paperbridge/paperbridge.env`; the
release-local launcher decodes it only for the Node process. It does not put the
value in a command argument, Git file, service log, or evidence file. The remote
file is root-owned mode `0600`.

The systemd unit runs as the non-login `paperbridge` user with no new
privileges, an empty capability set, private temporary storage, protected homes,
and a read-only system. It uses the VM system CA bundle for the standard MQTT/TLS
connection.

## Proxy and token

Set the proxy port and restate private visibility:

```sh
ssh exe.dev 'share port paperbridge-prod 3000'
ssh exe.dev 'share set-private paperbridge-prod'
```

Create a VM-scoped `X-Exedev-Authorization` token with an explicit finite
expiry. Store it in 1Password or another approved local secret store; do not
commit, paste, or log it. Use the token only at the exe.dev edge. The proxy
removes it before the request reaches Node.

Configure the service environment with both:

```text
PAPERBRIDGE_API_ALLOWED_HOST=api.paperbridge.tech
PAPERBRIDGE_API_ALLOWED_ORIGIN=https://api.paperbridge.tech
```

Confirm an anonymous and an invalid-token request fail at the proxy, then
confirm a valid token reaches `https://api.paperbridge.tech/health` and
`/ready`. Test an expired token when
it expires or by using a separately generated short-expiry token. Do not treat
edge access as a Paperbridge Invite or sender authorization.

## Deploy, inspect, and rollback

```sh
PAPERBRIDGE_SHA=<40-character-sha> just production-deploy
just production-status
just production-logs       # last 100 journald lines
just production-verify
just production-probe
```

The deploy workflow builds an isolated release directory, records the currently
running SHA as the explicit rollback target, then atomically switches the
`current` symlink. It refuses a new deploy while the current service is inactive,
so a failed change cannot overwrite the known rollback target. The
`paperbridge-dev-001` MQTT identity is the configured single Device identity
verified in the EMQX TLS spike; it is not a development VM credential.

To return to the recorded SHA:

```sh
just production-rollback
just production-verify
just production-probe
```

Restart and reboot checks must be no-output:

```sh
just production-restart
just production-verify
just production-probe
just production-reboot
# Wait for the VM to accept SSH, then run:
just production-verify
just production-probe
```

Record exact non-secret observations, SHAs, and commands. Do not run a print,
feed, cut, flash, or hardware action in this workflow. Physical output is issue
15 only.
