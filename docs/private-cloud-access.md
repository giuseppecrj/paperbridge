# Private cloud REST and MCP access

Use this guide to connect an approved private client to the deployed Paperbridge
service. It is not the VM deployment runbook; see
[`exedev-deployment.md`](exedev-deployment.md) for that workflow.

## Boundary

The current private endpoints are:

- REST: `https://api.paperbridge.tech/api/jobs`
- Streamable HTTP MCP: `https://api.paperbridge.tech/mcp`
- Process liveness: `https://api.paperbridge.tech/health`
- MQTT-client readiness: `https://api.paperbridge.tech/ready`

The exe.dev private proxy protects these endpoints. Non-browser clients send a
finite-expiry VM token on every request:

```text
X-Exedev-Authorization: Bearer <token>
```

Store the token in an approved local secret store or environment variable. Do
not commit it, paste it into tracked configuration, or distribute it as a
Sender credential. The deployment operator creates replacement tokens before
expiry; clients must be updated manually during that replacement.

This token grants private infrastructure access. It is **not** a Paperbridge API
key, Sender identity, Invite, or scoped permission. Paperbridge has no
application-level API-key or Sender-identity creation flow today. Do not give a
VM token to a person or application that should have limited send permission.

## Check access first

Set the token only in your current shell or other approved secret mechanism:

```sh
export PAPERBRIDGE_EXEDEV_VM_TOKEN='<token from the deployment owner>'
```

Check process liveness, then MQTT-client readiness:

```sh
curl --fail-with-body \
  -H "X-Exedev-Authorization: Bearer $PAPERBRIDGE_EXEDEV_VM_TOKEN" \
  https://api.paperbridge.tech/health

curl --fail-with-body \
  -H "X-Exedev-Authorization: Bearer $PAPERBRIDGE_EXEDEV_VM_TOKEN" \
  https://api.paperbridge.tech/ready
```

`/health` confirms that the Node process can serve HTTP. `/ready` confirms only
that its MQTT client is connected and subscribed to job results. Neither proves
that the Device or Printer is reachable, that a job was delivered, or that paper
emerged.

## Submit a REST job

`POST /api/jobs` accepts a complete `print-job.v1` object. The existing text and
feed fixture is a small example:

```sh
curl --fail-with-body \
  -H 'content-type: application/json' \
  -H "X-Exedev-Authorization: Bearer $PAPERBRIDGE_EXEDEV_VM_TOKEN" \
  --data-binary @packages/protocol/fixtures/print-job-v1/valid-text-feed.json \
  https://api.paperbridge.tech/api/jobs
```

This command submits real printing work. Run it only when the configured
Physical Inbox may receive the fixture output. For a new submission, use a new
`job_id`; do not treat an `unknown` result as permission to submit the work
again. A successful result is `delivered_to_printer`, not proof that paper
emerged. See [`protocol.md`](protocol.md) for the receipt contract and result
semantics.

## Add the MCP server

Configure a Streamable HTTP MCP client with the same private-proxy header. For
Pi-compatible client configuration, add an entry equivalent to this one to your
local MCP client configuration; do not commit the token:

```json
{
  "mcpServers": {
    "paperbridge": {
      "url": "https://api.paperbridge.tech/mcp",
      "headers": {
        "X-Exedev-Authorization": "Bearer ${PAPERBRIDGE_EXEDEV_VM_TOKEN}"
      },
      "auth": false
    }
  }
}
```

After the client connects, call `paperbridge_print` with a `content` receipt
object. The service generates the `job_id`, configured `device_id`, and
timestamp, then returns the same honest job result as REST. The tool can submit
real printing work; use it only for an approved recipient and never infer
`printed` from `delivered_to_printer`.

## When this access model is no longer enough

Ask for a Paperbridge authorization design before adding another independent
Sender, public sharing, untrusted automation, or a need to revoke one caller
without replacing other callers' access. That work requires an application-level
identity and permission model; it is not solved by sharing the exe.dev VM token.
