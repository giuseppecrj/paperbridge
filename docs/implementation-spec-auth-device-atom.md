# Paperbridge Auth, Device Claiming, and ATOM Target Specification

Status: agreed planning baseline; implementation has not started.

Date: 2026-08-08

## Goal

Allow a remote client to send a Semantic Print Job to a claimed Paperbridge
Device without a hardcoded exe.dev token, then support the M5Stack ATOM Lite as
a second Device target without changing the proven Waveshare/RP326 path.

The normal runtime path is:

```text
MCP/REST client
  -> WorkOS AuthKit OAuth
  -> Paperbridge API/MCP resource server on exe.dev
  -> EMQX MQTT/TLS
  -> Device Wi-Fi
  -> Device printer transport
  -> Printer
```

The Device has an outbound connection. It does not need an inbound port or a
computer running at the Owner's home. USB remains for provisioning and
operator diagnostics.

## Agreed domain model

### Account and Device

- A WorkOS authenticated User maps to a Paperbridge Account.
- An Account may be associated with many Devices.
- A Device is claimed by one Owner Account at a time.
- An Account may own some Devices and be a Guest on other Devices.
- Authorization is checked for the target `device_id` on every submission.
- WorkOS Organizations are not the Paperbridge authorization model.

A Device is the physical appliance. Its connected thermal printer remains a
separate Printer. A Device may therefore be an ATOM Lite target or the existing
ESP32-S3-ETH target without changing the Account model.

### Roles

- **Owner:** the Account that claims a Device. The Owner may manage the Device,
  its Guests, and its configuration operations allowed by the product.
- **Guest:** a per-Device membership with send-only permission. A Guest may
  submit a Semantic Print Job to that Device but may not manage the Device,
  claim it, transfer it, or manage other Guests.
- **Sender:** the authorization capability expressed by a Guest membership.
  Keep the product-facing term Guest while preserving the existing domain
  meaning that a Sender may submit output.

### OAuth tokens

- WorkOS/AuthKit owns user identity, OAuth authorization, and token issuance.
- Paperbridge validates tokens and maps the verified WorkOS `sub` to an Account.
- Multiple MCP clients or sessions may hold separate OAuth tokens for one
  Account.
- A token is not a Paperbridge Account, Invite, or Device membership.
- Paperbridge must not store or forward the MCP bearer token to MQTT or the
  Device. The API uses its own server-side MQTT credentials.

## Authentication and authorization

### WorkOS and MCP

WorkOS AuthKit is the OAuth authorization server. Paperbridge is the protected
resource server.

The `/mcp` resource server must:

1. expose Protected Resource Metadata;
2. challenge unauthenticated requests with `401` and `WWW-Authenticate`;
3. identify the configured AuthKit authorization server;
4. validate the JWT signature using WorkOS JWKS;
5. validate issuer, expiry, and the Paperbridge resource audience; and
6. map the verified `sub` to a Paperbridge Account before calling the MCP tool.

Configure the canonical public MCP URL as the WorkOS Resource Indicator. Enable
Client ID Metadata Documents for current MCP clients. Enable Dynamic Client
Registration only when a compatibility case requires it.

The MCP client must use standard OAuth discovery and bearer authentication. It
must not contain `X-Exedev-Authorization` or another infrastructure token.

### REST

`POST /api/jobs` must apply the same Account and Device authorization as MCP.
It must not remain an unauthenticated back door when `/mcp` is protected.

The exact REST audience and whether REST uses the same resource indicator as
MCP are an implementation detail to settle in the auth slice. Both routes must
produce the same Paperbridge authorization decision for the same Account and
Device.

### exe.dev boundary

The current exe.dev VM token is infrastructure access, not a Paperbridge
credential. It may remain in deployment/operator workflows, but it must not be
required by an end-user MCP client after OAuth cutover.

The deployment must provide a public HTTPS route that can reach the API/MCP
resource server and lets Paperbridge validate the WorkOS bearer token. Do not
solve this by forwarding the WorkOS token to exe.dev or MQTT.

## Device claiming and transfer

### Initial claim

1. The unclaimed Device exposes a one-time claim code through authorized local
   setup/provisioning.
2. The Owner signs in through WorkOS and submits the code to Paperbridge.
3. Paperbridge validates and consumes the code atomically.
4. The Device becomes owned by that Account.

The code is a human-friendly three-dashed-word value such as
`copper-lantern-otter`, not a bare three-digit code.

Claim codes must be:

- generated only through an authorized claim or transfer action;
- short-lived and one-use;
- high-entropy despite their readable format;
- stored hashed, never logged or returned after creation;
- rate-limited on verification; and
- invalidated when consumed, revoked, expired, or replaced.

A Device ID alone is never sufficient to claim a Device.

### Ownership transfer

Ownership transfer uses the same claim mechanism rather than a separate
multi-step transfer protocol:

1. The current Owner requests a new claim code for the Device.
2. The Owner sends the code to the intended recipient.
3. The recipient signs in to their Account and claims the Device with the code.
4. Paperbridge atomically replaces the Owner membership.
5. The previous Owner loses management access.

The current Owner must be the only party allowed to generate a transfer code.
A pending code may be revoked or replaced. A transfer must not partially apply.

Default security policy: remove prior Guest memberships when ownership changes.
The new Owner can invite those Accounts again. This policy should be confirmed
in the auth implementation issue before code is merged.

## Guest invitations

- An Owner creates a directional Invite for one target Account or authenticated
  recipient.
- The recipient accepts the Invite while authenticated with WorkOS.
- Acceptance creates a Guest membership for the specific Device.
- A Guest can submit jobs only to Devices where the Guest membership is active.
- An Owner can revoke a Guest membership without changing Device ownership.
- A Guest cannot create claim codes, transfer ownership, or manage other
  memberships.

Invite acceptance and claim-code redemption must be separate operations. An
Invite grants Guest access; a claim code changes Device ownership.

## Delivery and broker boundary

The existing cloud delivery path remains the baseline:

```text
Paperbridge API/MCP -> EMQX Serverless MQTT/TLS -> Device Wi-Fi -> Printer
```

- The API authorizes the Account against the requested Device before publish.
- The API publishes the existing semantic `print-job.v1` contract.
- The Device receives only its configured MQTT credentials and Device ID.
- The OAuth token, WorkOS `sub`, and Invite records do not cross into the
  Device protocol.
- Existing `job_id`, result, duplicate, unknown, and
  `delivered_to_printer` semantics remain unchanged.
- A successful device write is not proof that paper emerged.

## ATOM implementation boundary

The ATOM Lite is a separate firmware profile, not a replacement for the
Waveshare ESP32-S3/W5500/RP326 profile.

Reuse the semantic job validation, job service, coordinator, serial RPC
contract, host API, MQTT topics, and result vocabulary where compatible.
Replace the hardware composition with:

- ESP32 Wi-Fi and MQTT/TLS;
- UART 9600 8N1 to the kit printer;
- the ATOM GPIO 23/33 UART mapping;
- conservative memory and message limits; and
- no cutter capability.

First ATOM delivery milestone:

- remote text and feed jobs over the authenticated API/MCP → EMQX → ATOM path;
- no raster, QR, TLS-sized maximum payload, or cut claim until measured and
  physically validated; and
- no change to the current Waveshare/RP326 deployment or protocol behavior.

USB/UART and fake-transport tests are the first engineering checks. They are
not a substitute for ATOM hardware or paper verification.

## Implementation slices

### Slice 1: authorization model

- Define Account, Device, Device membership, Invite, and claim-code records.
- Add Owner and send-only Guest authorization decisions.
- Add tests for owner, guest, revoked guest, wrong-device, and unclaimed-device
  cases.

### Slice 2: WorkOS OAuth resource server

- Add WorkOS JWT/JWKS validation and `sub` to Account mapping.
- Add MCP protected-resource metadata and bearer challenge.
- Remove the MCP hardcoded exe.dev token from the application client path.
- Protect REST and MCP consistently.
- Add discovery, invalid-token, wrong-audience, expiry, and multi-token tests.

### Slice 3: claim and transfer

- Add one-time three-word claim-code generation, hashing, expiry, rate limits,
  revocation, and atomic consumption.
- Add initial claim and Owner-generated transfer-code flows.
- Add Guest Invite acceptance and revocation.
- Add tests proving old Owner/Guest access is removed after transfer according
  to the final transfer policy.

### Slice 4: authenticated cloud acceptance

- Run the API on the existing exe.dev deployment behind a public HTTPS route
  suitable for OAuth.
- Keep EMQX Serverless as the MQTT/TLS broker.
- Verify one Account with multiple OAuth client/session tokens.
- Verify owner and Guest submissions target the correct Device.
- Verify unauthorized targets never publish to MQTT.

### Slice 5: ATOM target

- Add the ATOM profile and fake UART transport.
- Host-test remote text/feed submission through the authenticated cloud path.
- Perform the separately authorized USB, UART, Wi-Fi, MQTT/TLS, and printer
  validation sequence from the ATOM research note.

## Non-goals

This specification does not add:

- public anonymous printing;
- WorkOS Organization-based authorization;
- device-side OAuth or WorkOS credentials;
- MQTT access for end-user clients;
- durable Device-side queues;
- automatic physical-output retry;
- multiple simultaneous printers on one Device; or
- a claim code that can be guessed from a Device ID.

## Verification gates

Before ATOM hardware work:

- OAuth discovery and JWT validation pass host tests.
- REST and MCP enforce the same per-Device Owner/Guest rules.
- Multiple OAuth tokens map to one Account without creating duplicate Accounts.
- Claim and transfer codes are one-use, expiring, rate-limited, and atomic.
- A transferred Device cannot be managed by its previous Owner.
- Unauthorized jobs do not reach EMQX.
- The existing Waveshare/RP326 host and simulator suites remain green.

Physical ATOM results must be recorded separately as documented, host-tested,
simulator-tested, or physically verified. No cloud or host result may be called
paper output.

## Source documents

- `CONTEXT.md`
- `docs/architecture.md`
- `docs/security.md`
- `docs/protocol.md`
- `docs/research/workos-authkit-mcp-oauth-2026-08-07.md`
- `docs/research/exedev-mcp-auth-2026-08-07.md`
- `docs/research/atom-printer-paperbridge-2026-08-08.md`
- `docs/emqx-tls-spike.md`
- `docs/private-cloud-access.md`
- `docs/adr/0007-use-exe-dev-and-managed-mqtt-for-the-phase-2-mvp.md`
