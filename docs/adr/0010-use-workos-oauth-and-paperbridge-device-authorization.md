# ADR 0010: Use WorkOS OAuth and Paperbridge device authorization

- Status: Accepted
- Date: 2026-08-08
- Supersedes: the private end-user credential and single-device authorization
  boundaries in ADR 0007; ADR 0007's exe.dev and EMQX deployment decision
  remains in force

## Context

Paperbridge currently protects the private REST and MCP endpoints with an
exe.dev VM-scoped token. That token is infrastructure access, not a Paperbridge
identity or Sender permission. It cannot support multiple OAuth clients for one
Account, per-Device Guest access, ownership transfer, or revocation of one
client without changing infrastructure access for every client.

The next Device target is the M5Stack ATOM Lite. It must receive jobs through
an internet path without a computer at the Owner's home. The API/MCP service
must therefore authorize the Account and target Device before publishing the
existing semantic job to EMQX. The Device must not receive end-user OAuth
credentials.

## Decision

Use WorkOS AuthKit as the OAuth authorization server and Paperbridge as the
protected resource server for REST and MCP.

Paperbridge will own the application authorization model:

- a WorkOS authenticated User maps to a Paperbridge Account;
- an Account may own multiple Devices;
- an Account may be a Guest on other Devices;
- an Owner claims and manages a Device;
- a Guest has send-only access to the specific Device;
- Invites are directional Paperbridge records; and
- a Device claim or transfer uses a one-time, short-lived, three-dashed-word
  claim code.

The current Owner generates a transfer claim code. The recipient signs in and
redeems it. Redemption atomically replaces ownership and removes the previous
Owner's management access. Prior Guest cleanup is an implementation-policy
choice recorded in the implementation specification and must be finalized
before the transfer code is merged.

Paperbridge will validate WorkOS JWTs using issuer, signature/JWKS, expiry, and
resource-audience checks. The MCP resource server will expose protected-resource
metadata and the standard bearer challenge. REST and MCP will enforce the same
per-Device authorization decision.

The exe.dev VM token remains only for infrastructure and operator workflows. It
must not be required by an end-user MCP client after OAuth cutover. The API
uses server-side MQTT credentials to publish to EMQX; it never forwards a
WorkOS bearer token to MQTT or a Device.

The existing exe.dev application service and EMQX Serverless MQTT/TLS path
remain the deployment baseline. The ATOM Lite is added later as a separate
firmware profile and does not change the existing Waveshare ESP32-S3/W5500/RP326
path.

## Options considered

### Keep the exe.dev VM token for clients

Rejected. It grants infrastructure access rather than Account and Device
permissions. All holders are effectively equivalent and it cannot provide
standard MCP OAuth discovery or per-client revocation.

### Use WorkOS Organizations as Paperbridge authorization

Rejected. WorkOS authenticates the User, but Paperbridge owns physical Device
claims, Owner/Guest membership, Invites, and per-Device authorization. This
keeps the domain model independent of WorkOS organization membership.

### Put OAuth credentials on the Device

Rejected. Devices use their own MQTT credentials and receive already-authorized
semantic jobs. End-user identity and authorization remain at the API boundary.

### Add public anonymous printing

Rejected. Authentication is required. A valid Account must have Owner or Guest
permission for the target Device.

## Consequences

Positive:

- Multiple OAuth clients or sessions can use one Account without creating
  duplicate Accounts.
- A Guest can be revoked for one Device without changing other memberships.
- Device ownership can transfer through the existing claim mechanism.
- MCP clients no longer need a hardcoded infrastructure token.
- The ATOM and existing Device targets share one authorized cloud path.

Costs and risks:

- The API must implement OAuth resource-server behavior, discovery, JWT/JWKS
  validation, and audience checks.
- The current exe.dev private-proxy route must be replaced or supplemented by
  an HTTPS route suitable for OAuth clients. The VM token remains in deployment
  workflows during migration.
- Paperbridge needs persistent Account, Device membership, Invite, and claim
  code state before authorization can be enforced reliably.
- Claim codes need high entropy, hashing, expiry, rate limiting, revocation,
  and atomic consumption even though their display format is simple.
- Existing private access documentation and MCP client configuration become a
  migration path, not the final end-user authentication model.

## Implementation boundaries

The agreed implementation specification is
`docs/implementation-spec-auth-device-atom.md`. It defines the dependent
slices:

1. Account, Device, membership, Invite, and claim-code authorization model;
2. WorkOS OAuth resource server for MCP and REST;
3. claim, transfer, and Guest flows;
4. authenticated exe.dev and EMQX cloud acceptance; and
5. the separate ATOM firmware target.

No physical ATOM operation is implied by this decision. Hardware work remains
subject to the research note's explicit authorization and evidence gates.
