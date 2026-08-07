# Smallest secure authentication design for Paperbridge MCP/REST on exe.dev

Research performed 2026-08-07 against official MCP specification pages, official
exe.dev documentation, the installed MCP TypeScript SDK v2.0.0 types and client
source, the installed Pi `pi-mcp-adapter` README/types, and the current
`apps/api` implementation. These are documentation and code facts, not a
deployment decision, production SLA, or physical verification.

## Workload under study

`apps/api` is a private single-device Node.js service that today:

- binds `127.0.0.1` by default (`PAPERBRIDGE_API_HOST`, default port 3000);
- exposes `POST /api/jobs` with **no application authentication**;
- exposes Streamable HTTP MCP at `/mcp` with **no application authentication**;
- mounts MCP through official v2 `createMcpHandler` + `toNodeHandler`;
- rejects non-loopback `Host` and non-loopback `Origin` on `/mcp` via
  `localhostHostValidation()` / `localhostOriginValidation()`;
- holds a long-lived outbound MQTT client and waits for correlated results.

Sources: `apps/api/README.md`, `apps/api/src/server.ts`,
`apps/api/src/api-server.ts`, `apps/api/src/mcp-server.ts`, `docs/security.md`.

This report answers: **if** Paperbridge hosts that process on an exe.dev VM
behind `https://<vm>.exe.xyz`, what is the smallest secure authentication design
for one operator now, and how it migrates to multi-sender authorization later.

Related prior research (runtime/hosting, not auth):
`docs/research/cloud-compute-api-runtime-2026-08-07.md`.

## Decision summary

### One-operator MVP (recommended)

**Keep the exe.dev HTTP proxy private. Authenticate non-browser clients with a
VM-scoped exe.dev HTTPS token on `X-Exedev-Authorization`. Do not implement
MCP OAuth or an application bearer token yet. Do not mark the share public.**

Concrete shape:

1. Run `apps/api` on the VM, bound to loopback or a port that only the exe.dev
   edge proxy reaches (default private proxy).
2. Point the proxy at that port with `ssh exe.dev share port <vm> <port>`; leave
   visibility **private** (`share set-private` if it was ever public).
3. Generate a **VM-scoped** token:
   `ssh exe.dev ssh-key generate-api-key --vm=<vm> --label=paperbridge-mcp`
   with an explicit `exp`.
4. Configure Pi MCP (and any other Streamable HTTP client) to send:
   `X-Exedev-Authorization: Bearer <vm-token>`
   on every request to `https://<vm>.exe.xyz/mcp`.
5. Use the same header for REST:
   `curl -H 'X-Exedev-Authorization: Bearer <token>' ... /api/jobs`.
6. **Change the current localhost-only Host/Origin guards** before any remote
   mount works: allow the public hostname (for example `<vm>.exe.xyz`) and keep
   rejecting arbitrary hosts. Origin may stay absent for non-browser clients.
7. Trust model for MVP: **edge authentication only**. The Node process still has
   no app-level auth. That is acceptable only while the edge is private **and**
   the process is not reachable on a public path.

Why this is smallest and still secure for one operator:

- Authorization is **optional** in MCP; HTTP transports **SHOULD** use OAuth 2.1
  when they support authorization, but a private edge gate with no public
  audience is a network access control, not an MCP resource-server
  implementation.
- exe.dev documents non-browser access specifically for this case: browser
  cookies are the default private-proxy path; VM tokens exist for API clients.
- Pi MCP adapter already supports arbitrary custom headers and static bearer
  tokens without OAuth.
- Official `StreamableHTTPClientTransport` accepts both `requestInit.headers`
  and `authProvider` (which sets `Authorization: Bearer …`).
- Preferred exe.dev client header is `X-Exedev-Authorization`, which the proxy
  **consumes and strips** before the request reaches the VM — so it does not
  collide with a later application `Authorization` bearer.

### Explicit non-goals for MVP

- Standard MCP OAuth (Protected Resource Metadata, AS discovery, PKCE, DCR).
- Application-level shared secret on `/mcp` and `/api/jobs`.
- Public share (`share set-public`).
- Login-with-exe browser cookies as the primary MCP client path.
- Multi-sender identity, per-sender rate limits, or audit of distinct senders.
- Tailscale as a required dependency (optional extra layer only).

### Later sender authorization (migration path)

When more than one trusted human/agent must print, or when the URL must be
public/shareable without exe.dev account access:

1. Keep TLS at the edge.
2. Add **application bearer** (shared secret or per-client token) checked in
   Node **before** REST body parse and before MCP handler — same gate for
   `/api/jobs` and `/mcp`.
3. Or implement full **MCP OAuth 2.1 resource server** for `/mcp` only, plus a
   separate REST auth scheme; only when third-party MCP clients require the
   standard discovery flow.
4. Prefer **not** to use Login-with-exe cookies as the sole gate for MCP: they
   are browser-oriented.

## Current code facts (repo)

| Surface | Auth today | Host/Origin | Notes |
| --- | --- | --- | --- |
| `POST /api/jobs` | None | None | Any caller that can reach the socket may submit a job. |
| `/mcp` | None | Loopback Host + Origin only | DNS-rebinding defense for localhost bind. |
| Bind | `127.0.0.1` default | N/A | `docs/security.md` states future non-loopback/Tailscale bind needs explicit allowed-host/origin policy. |
| Delivery semantics | N/A | N/A | Success is `delivered_to_printer`, not `printed`. |

Sources: `apps/api/src/api-server.ts`, `apps/api/src/mcp-server.ts`,
`apps/api/src/server.ts`, `docs/security.md`.

**Blocker for remote hosting without code change:**
`localhostHostValidation()` / `localhostOriginValidation()` will reject
`Host: <vm>.exe.xyz`. A remote mount **must** replace or parameterize those
allow-lists. Official SDK docs require Host/Origin validation in front of the
handler; they do not require that the allow-list stay loopback forever.

Source: MCP TypeScript SDK “Serve over HTTP”
<https://ts.sdk.modelcontextprotocol.io/v2/serving/http.html>;
`@modelcontextprotocol/node` README (installed v2.0.0).

## (1) Official MCP authorization requirements

### Protocol posture

From the current MCP Authorization specification (2025-06-18 and draft):

- Authorization is **OPTIONAL**.
- When supported on HTTP-based transports, implementations **SHOULD** conform to
  the authorization specification.
- STDIO transports **SHOULD NOT** use this OAuth flow; they take credentials from
  the environment.
- Protected MCP servers act as **OAuth 2.1 resource servers**.
- MCP clients act as **OAuth 2.1 clients**.
- Authorization server details are out of scope of the resource server; AS may
  be co-hosted or separate.

Normative pieces when authorization **is** implemented:

- OAuth 2.1 (draft), Bearer tokens (RFC 6750).
- Protected Resource Metadata (RFC 9728) — MCP servers **MUST** implement it;
  clients **MUST** use it for AS discovery.
- Authorization Server Metadata (RFC 8414) and/or OpenID Connect Discovery —
  clients **MUST** support discovery.
- Access tokens go in the `Authorization` request header on **every** HTTP
  request; **not** in the query string.
- Resource Indicators (RFC 8707): clients **MUST** send `resource` identifying
  the MCP server; servers **MUST** validate audience.
- 401 / 403 / 400 status codes for auth failures.
- Token passthrough is forbidden: servers **MUST NOT** accept tokens not issued
  for them.

Sources:

- <https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization>
- <https://modelcontextprotocol.io/specification/draft/basic/authorization.md>
- <https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/authorization>
- Security best practices (token passthrough, confused deputy):
  <https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices>

### Implication for Paperbridge MVP

A **private** exe.dev edge that never exposes the MCP URL to anonymous internet
users is **network access control**, not “MCP authorization supported.” That is
compatible with OPTIONAL authorization.

The moment the endpoint is reachable by arbitrary clients (public share, leaked
URL without edge auth, or third-party MCP clients that expect standard OAuth),
Paperbridge should either:

- keep a non-OAuth shared secret **and** accept that non-spec clients must be
  configured with static headers; or
- implement the full resource-server profile.

Do **not** half-implement OAuth (for example return 401 without
`WWW-Authenticate` / PRM) if clients are expected to auto-discover.

## (2) MCP clients and `StreamableHTTPClientTransport` vs exe.dev headers

### Official TypeScript client transport (installed `@modelcontextprotocol/client@2.0.0`)

`StreamableHTTPClientTransportOptions` supports:

- `requestInit?: RequestInit` — custom fetch options, including **headers**.
- `authProvider?: AuthProvider | OAuthClientProvider` — `token()` is called
  before every request; the transport sets  
  `headers['Authorization'] = \`Bearer ${token}\``.
- Optional custom `fetch`.

Installed client source (`packages/client/src/client/streamableHttp.ts` as
shipped in the package / mirrored on GitHub) merges `_requestInit` into
requests and, when an auth provider returns a token, sets the standard
`Authorization: Bearer` header.

Sources:

- Installed package types: `StreamableHTTPClientTransportOptions`,
  `AuthProvider`.
- Client source behavior: Authorization header assignment around the transport
  request path
  (<https://github.com/modelcontextprotocol/typescript-sdk/blob/main/packages/client/src/client/streamableHttp.ts>).
- API docs:
  <https://ts.sdk.modelcontextprotocol.io/v2/api/@modelcontextprotocol/client/client/streamableHttp.html>

### Mapping to exe.dev authentication methods

| exe.dev method (VM HTTPS proxy) | Client can send it? | Notes |
| --- | --- | --- |
| **`X-Exedev-Authorization: Bearer <token>` (preferred)** | **Yes** via `requestInit.headers` or any client custom-header config | Proxy **consumes and strips** this header before the VM sees it. |
| **`Authorization: Bearer <token>` (deprecated for exe.dev)** | **Yes** via `authProvider` or headers | Collides with future app/MCP OAuth bearer use; exe.dev prefers the X- header. |
| **HTTP Basic** (username ignored; password = token) | **Yes** if the client can set `Authorization: Basic …` | Documented for tools like git; awkward for MCP SDK defaults. |
| **Browser login cookie** | Automatic in browsers only | Not available to ordinary MCP SDK / Pi HTTP clients. |

exe.dev sources:

- <https://exe.dev/docs/https-tokens-for-vms>
- <https://exe.dev/docs/https-api>
- <https://exe.dev/docs/proxy>
- <https://exe.dev/docs/login-with-exe>

**Conclusion:** Official Streamable HTTP clients **can** authenticate to a
private exe.dev proxy without browser cookies, by sending the preferred
`X-Exedev-Authorization` header. They are **not** limited to MCP OAuth.

## (3) Pi MCP configuration and custom headers

Installed adapter: `pi-mcp-adapter` (user-global Pi agent install).

Documented HTTP server fields include:

- `url` — Streamable HTTP endpoint (SSE fallback).
- `headers` — arbitrary HTTP headers; supports `${VAR}` / `$env:VAR`; leading
  `!command` secret resolution at connect time.
- `auth`: `"bearer"` | `"oauth"` | `false`.
- `bearerToken` / `bearerTokenEnv` — static bearer; adapter sets
  `Authorization: Bearer <token>` when resolving bearer auth.
- OAuth sub-config for full MCP OAuth when required.

Implementation detail (adapter `server-manager.ts`): headers are resolved into
`requestInit = { headers }`, and bearer auth adds `Authorization`. That object
is passed into `StreamableHTTPClientTransport` options together with an optional
OAuth `authProvider`.

Example shape for MVP (illustrative; do not commit secrets):

```json
{
  "mcpServers": {
    "paperbridge": {
      "url": "https://<vm>.exe.xyz/mcp",
      "headers": {
        "X-Exedev-Authorization": "Bearer ${PAPERBRIDGE_EXEDEV_VM_TOKEN}"
      },
      "auth": false
    }
  }
}
```

Notes:

- Set `auth: false` (or rely on “custom headers configured” behavior) so the
  adapter does not auto-start OAuth against a server that does not implement
  MCP OAuth.
- Prefer `headers` + `X-Exedev-Authorization` over `auth: "bearer"`, because
  bearer mode targets `Authorization`, which exe.dev marks deprecated for VM
  proxy auth and which you will want free for later app tokens.
- Secrets: env interpolation or `!fnox …` / `!op read …` style command
  resolution is supported by the adapter; keep tokens out of committed JSON.

Sources: installed `pi-mcp-adapter/README.md`, `types.ts`, `server-manager.ts`.

## (4) exe.dev private proxy, VM tokens, Login with exe.dev, public sharing, header stripping

### Private vs public proxy

- Default: **private**. Only users with access to the VM can use the HTTP proxy.
- First browser visit to `https://vmname.exe.xyz/` redirects to exe.dev login.
- `share set-public <vm>` makes the proxy reachable **without** login.
- `share set-private <vm>` restores private access.
- Alternate ports 3000–9999 are reachable as `https://vmname.exe.xyz:port/` and
  remain restricted to users with VM access; only one primary port may be marked
  public.

Source: <https://exe.dev/docs/proxy>

### Sharing mechanisms (identity at the edge)

1. Public share — anyone, no login.
2. `share add <vm> <email>` — invite specific emails; they log into exe.dev.
3. `share add-link <vm>` — link grants access after register/login; revoking the
   link does **not** remove already-added users; remove with
   `share remove <vm> <email>`.

Source: <https://exe.dev/docs/sharing>

### VM-scoped HTTPS tokens (non-browser)

- Generated with `ssh exe.dev ssh-key generate-api-key --vm=…` (or local SSH
  signing with VM namespace `v0@VMNAME.exe.xyz`).
- Preferred client header: **`X-Exedev-Authorization: Bearer <token>`**.
- Deprecated: `Authorization: Bearer <token>`.
- Basic auth: password = token (VM proxy).
- Proxy **strips** `X-Exedev-Authorization` after authentication.
- Authenticated requests reach the VM with:
  - `X-ExeDev-UserID`
  - `X-ExeDev-Email`
  - `X-ExeDev-Token-Ctx` (signed `ctx` from token payload, if present)
- Token payload fields include `exp`, `nbf`, `cmds` (for exe.dev API commands),
  and free-form `ctx`. Docs **strongly recommend** setting `exp`. Default `exp`
  is “distant future” if omitted — avoid that for Paperbridge.
- Invalid/expired token → HTTP 401 at the edge.

Sources: <https://exe.dev/docs/https-tokens-for-vms>,
<https://exe.dev/docs/https-api>

### Login with exe.dev (browser)

- For apps that want identity headers without managing passwords.
- Injects `X-ExeDev-UserID` and `X-ExeDev-Email` when authenticated.
- Login URL: `/__exe.dev/login?redirect={path}`; logout POST
  `/__exe.dev/logout` clears the **cookie**.
- Private sites always have authentication headers once access is granted;
  public sites only have headers when the user is logged in.
- Complementary to sharing, not a substitute for API tokens.

Source: <https://exe.dev/docs/login-with-exe>

### Forwarded headers (proxy trust)

Proxied requests include:

- `X-Forwarded-Proto`
- `X-Forwarded-Host`
- `X-Forwarded-For`

Source: <https://exe.dev/docs/proxy>

**Trust implication:** any app-level auth that keys off `X-ExeDev-*` or
`X-Forwarded-*` is only safe if **untrusted clients cannot hit the Node port
directly**. Bind the process so only the exe.dev proxy (or localhost) can
connect. Do not treat client-supplied forged `X-ExeDev-Email` as proof of
identity on a publicly reachable origin port.

## (5) Browser login/cookies vs non-browser MCP clients

| Client class | Private proxy browser cookie | VM token header | App bearer / MCP OAuth |
| --- | --- | --- | --- |
| Browser fetch to private URL | Works after login redirect | Optional | Optional |
| Pi `pi-mcp-adapter` HTTP | **No cookie jar / login flow for exe.dev** | **Yes** via `headers` | Yes (`auth: bearer` / `oauth`) |
| Official `StreamableHTTPClientTransport` | No | **Yes** (`requestInit`) | Yes (`authProvider`) |
| `curl` / automation | No (unless cookie jar scripted) | **Yes** | Yes |
| Paperbridge tests (`call-mcp.ts`) | N/A localhost | N/A | N/A today |

**Conclusion:** Login-with-exe cookies are **not** a viable primary control for
Pi or SDK MCP clients. VM tokens or application credentials are required for
those clients even when the proxy is private.

## (6) Options compared

| Option | What protects the printer path | Fits one-operator MVP? | Multi-sender later? | Client config | Main risk |
| --- | --- | --- | --- | --- | --- |
| **A. Private exe.dev edge + VM token only (recommended MVP)** | Edge login/token; process unauthenticated | **Yes** | Weak: all holders of any valid edge credential are equal | Pi `headers.X-Exedev-Authorization` | Public share by mistake; direct bind exposure; no per-sender audit |
| **B. Standard MCP OAuth** | Resource server validates AS-issued bearer | Overkill now | Strong for MCP clients | Pi `auth: oauth` | Large implementation: PRM, AS, PKCE, audience, rotation |
| **C. Application bearer (shared or per-client)** | Node checks `Authorization` before job/MCP | Optional hardening | Good intermediate | Pi `auth: bearer` or headers | Secret distribution; must not skip REST |
| **D. Guest Tailscale / overlay VPN** | Network membership | Possible extra layer | Membership ≠ sender auth | Usually no HTTP secret | Not documented as an exe.dev product feature; ops on the VM; still need app policy later |
| **E. Layered: private edge + app bearer** | Edge + app | Slightly more than minimal | Yes | Two credentials or edge-only for owner + app for guests | Complexity; only needed when edge identity is insufficient |
| **F. Public share + app bearer only** | App secret only | Not for first remote | Possible | Bearer | Secret leak = open printer; no edge help |
| **G. Public share + Login-with-exe allowlist in app** | Email header allowlist | Poor for MCP | Browser-only senders | Cookie | MCP clients lack cookies; header forgery if direct bind |

### Recommendation ranking

1. **MVP:** A (private edge + VM token), with Host allow-list fix.
2. **First multi-client step:** E or C (app bearer in Node for both routes).
3. **Third-party MCP ecosystem:** B (full OAuth RS) when discovery is required.
4. **D** only as optional network isolation, never as the sole authorization
   story for distinct senders.
5. Avoid **F** and **G** as primary designs for agent/MCP ingress.

## (7) Threat model: `/mcp` and `POST /api/jobs`

Assets:

- Ability to enqueue semantic print jobs that the device may deliver to a
  physical printer.
- MQTT credentials and broker reachability from the API process.
- Job content (text/images) confidentiality and integrity in transit.

Actors:

- Operator (trusted).
- Additional invited exe.dev users / share-link users.
- Internet anonymous clients.
- Malicious web page (DNS rebinding / CSRF-like browser calls).
- Compromised MCP client host.
- Co-tenant or local process on the VM.

### Shared threats

| Threat | MVP mitigation | Residual risk |
| --- | --- | --- |
| Anonymous internet POST job/MCP | Private proxy default; no `set-public` | Operator error publishing share |
| Stolen VM token | Short `exp`; store in 1Password/Fnox; regenerate | Until expiry, full access |
| Token in shell history / committed config | Env/`!command` resolution; never commit | Operator discipline |
| Direct hit to Node port bypassing edge | Bind `127.0.0.1` or firewall so only proxy path works | Mis-bind `0.0.0.0` without edge |
| Forged `X-ExeDev-*` if port exposed | Do not trust identity headers unless peer is proxy-only | Misconfiguration |
| DNS rebinding / bad Host | Parameterized Host allow-list (`<vm>.exe.xyz`, localhost for dev) | Missing allow-list update |
| Browser Origin attacks | Origin allow-list; non-browser clients omit Origin (SDK allows absent Origin) | Over-permissive Origin list |
| Oversized body / schema abuse | Existing body limit + semantic validation | Still consumes MQTT/device after auth |
| Confused deputy / OAuth mix-up | N/A until OAuth | Follow MCP security best practices when adding OAuth |
| Token passthrough to MQTT | Never forward client tokens to broker; use server MQTT creds | Keep separation |

### Route-specific notes

**`/mcp`**

- Tool `paperbridge_print` generates `job_id` / `device_id` / timestamp server-
  side; clients supply receipt `content` only.
- Stateless per-request handler; auth must run **per HTTP request**, not once
  per “session” assumption.
- MCP SDK does **not** verify tokens inside `createMcpHandler`; verification is
  always outer middleware (`authInfo` is pass-through).

Source: <https://ts.sdk.modelcontextprotocol.io/v2/serving/http.html>

**`POST /api/jobs`**

- Accepts a full source `print-job.v1` body (client-chosen `job_id`).
- Today has **no** Host/Origin guard (unlike MCP). Remote exposure without app
  or edge auth is full job submission.
- Any future app auth must cover this route with the **same** strength as MCP;
  protecting only `/mcp` is insufficient.

### Proxy trust rules (implementation checklist)

1. Edge authenticates (private share and/or VM token).
2. Process listens on loopback **or** interface only the platform proxy can
   reach.
3. Host allow-list includes the public hostname clients use.
4. Do not enable public share for MVP.
5. If app later trusts `X-ExeDev-Email`, also verify the request could only have
   come through the proxy (bind + optional shared proxy secret if exe.dev ever
   provides one; today identity headers are documented as added by the proxy
   after its own auth).
6. Prefer application secrets in `Authorization` for app-level policy so they
   are not stripped; keep exe.dev tokens on `X-Exedev-Authorization`.

## (8) Secret rotation and multi-client implications

### exe.dev VM tokens

- Embed `exp` / `nbf`; default long life is unsafe for Paperbridge.
- Rotation procedure: generate new labeled token → distribute to clients →
  remove/stop using old token after overlap window.
- Docs describe generation and 401 on invalid/expired tokens; treat
  **expiry + replacement** as the primary revocation mechanism unless exe.dev
  later documents explicit token revoke APIs for VM HTTPS tokens.
- `ctx` can differentiate tokens (for example `{"client":"pi-home"}`) and is
  forwarded as `X-ExeDev-Token-Ctx` for optional app logging — not a substitute
  for per-sender authz.

### MQTT credentials

- Remain server-side (`PAPERBRIDGE_MQTT_*`). Clients never receive them.
- Rotate independently of edge tokens via Fnox/1Password and process restart
  (existing project secret workflow).

### Multi-client

| Stage | Credential model | Rotation blast radius |
| --- | --- | --- |
| One operator | One VM token (or operator browser login + one token for Pi) | All operator clients |
| Few trusted senders | Per-client VM tokens (different labels/`ctx`) **or** per-client app bearers | One client |
| Public / third-party MCP | MCP OAuth access tokens + refresh; short TTL | Single user session |

Avoid a single immortal shared app secret once more than one administrative
domain exists.

## Exact blockers and tests

### Blockers before any remote MVP works

1. **Host validation** still loopback-only in `createMcpEndpoint` — remote Host
   fails closed.
2. **No documented production bind** for proxy-fronted mode (must not leave
   unauthenticated process on `0.0.0.0` if the proxy is public or bypassed).
3. **Operator runbook** for private share + VM token + Pi header config (not
   code, but required for secure ops).
4. **MQTT path from VM** to broker must already work (hosting concern; see cloud
   runtime research). Auth design does not fix broker reachability.

### Tests to add when implementing (not done in this research)

Host-tested, no hardware required:

1. **Host allow-list:** request with `Host: <allowed>` reaches MCP; other hosts
   → 403.
2. **Origin allow-list:** disallowed Origin → 403; missing Origin allowed for
   non-browser.
3. **Unauthenticated edge simulation:** if app bearer is added, missing/wrong
   token → 401 on **both** `/mcp` and `/api/jobs`.
4. **MCP tool still submits** with valid outer auth (existing MCP tests + header).
5. **REST job still submits** with same outer auth.
6. **No regression** on localhost defaults for local dev.
7. If trusting `X-ExeDev-Email`, unit-test that header is ignored unless a
   “proxy trust” mode is enabled (prevents local spoofing in tests/dev).

Physical/manual acceptance (operator):

1. Private URL without token/login fails from a logged-out browser.
2. Pi with `X-Exedev-Authorization` can call `paperbridge_print`.
3. `curl` with the same header can `POST /api/jobs`.
4. After token expiry, both fail at the edge with 401.
5. Confirm process is not reachable on a public IP:port bypassing exe.dev.

## Recommended end-to-end design (MVP)

```text
Pi / curl
  |  HTTPS
  |  X-Exedev-Authorization: Bearer <vm-scoped token>
  v
exe.dev private HTTP proxy  (TLS terminate, authn, strip X-Exedev-Authorization)
  |  inject X-ExeDev-UserID / Email / Token-Ctx
  |  X-Forwarded-*
  v
apps/api on VM (loopback bind)
  Host allow-list: <vm>.exe.xyz (+ localhost for local)
  /mcp  -> MCP handler (no app OAuth yet)
  /api/jobs -> REST (no app auth yet)
  v
MQTT -> device -> printer  (unchanged honesty: delivered_to_printer only)
```

Pi config sketch:

```json
{
  "mcpServers": {
    "paperbridge": {
      "url": "https://<vm>.exe.xyz/mcp",
      "headers": {
        "X-Exedev-Authorization": "Bearer ${PAPERBRIDGE_EXEDEV_VM_TOKEN}"
      },
      "auth": false
    }
  }
}
```

REST sketch:

```sh
curl -sS \
  -H "content-type: application/json" \
  -H "X-Exedev-Authorization: Bearer $PAPERBRIDGE_EXEDEV_VM_TOKEN" \
  --data-binary @packages/protocol/fixtures/print-job-v1/valid-text-feed.json \
  "https://<vm>.exe.xyz/api/jobs"
```

### Migration path

| Stage | Trigger | Change |
| --- | --- | --- |
| 0 Local | Current | Loopback, no auth (status quo). |
| 1 Remote operator | Host on exe.dev | Private proxy + VM token + Host allow-list; still no app auth. |
| 2 Second client / shared automation | Need independent revoke | Per-client VM tokens or introduce app bearer on both routes. |
| 3 External senders / public URL | Product requirement | App auth mandatory; prefer per-client tokens; optional public share **only** with app auth. |
| 4 Ecosystem MCP clients | Need OAuth discovery | MCP OAuth RS on `/mcp`; keep REST on its own scheme; never token-passthrough to MQTT. |

## What not to build yet

- Authorization server, DCR, PRM documents.
- Cookie-based Login-with-exe as the only MCP gate.
- Public anonymous MCP “demo” endpoint.
- Trusting `X-ExeDev-Email` without proxy-only bind.
- Using deprecated edge `Authorization` bearer if an app bearer is planned next.

## Source register (this research)

| Topic | Primary source | Recorded fact |
| --- | --- | --- |
| MCP auth optional / OAuth 2.1 RS | <https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization> | Authorization optional; HTTP SHOULD conform when supported; Bearer on every request; PRM required when protected. |
| MCP draft auth | <https://modelcontextprotocol.io/specification/draft/basic/authorization.md> | Same core model; expanded discovery/registration guidance. |
| MCP security BP | <https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices> | Token passthrough forbidden; confused-deputy mitigations for OAuth proxies. |
| MCP TS HTTP serve | <https://ts.sdk.modelcontextprotocol.io/v2/serving/http.html> | Handler does not verify Host/Origin/token; mount guards outside; `authInfo` pass-through. |
| StreamableHTTPClientTransport | installed `@modelcontextprotocol/client@2.0.0` + SDK docs | `requestInit` + `authProvider`; authProvider sets `Authorization: Bearer`. |
| `@modelcontextprotocol/node` guards | installed package README/d.ts | `hostHeaderValidation` / `originValidation`; missing Origin allowed. |
| exe.dev proxy | <https://exe.dev/docs/proxy> | Private default; public share commands; X-Forwarded-*; alt ports. |
| exe.dev sharing | <https://exe.dev/docs/sharing> | Public, email invite, share-link semantics. |
| exe.dev VM tokens | <https://exe.dev/docs/https-tokens-for-vms> | Preferred `X-Exedev-Authorization`; strip at proxy; Basic supported; identity headers to VM. |
| exe.dev HTTPS API tokens | <https://exe.dev/docs/https-api> | `exp`/`nbf`/`ctx`; recommend setting `exp`. |
| Login with exe.dev | <https://exe.dev/docs/login-with-exe> | Cookie login/logout; email/user headers; browser-oriented. |
| Pi MCP adapter | installed `pi-mcp-adapter` README/types/server-manager | `headers`, `auth` bearer/oauth, `requestInit` wiring. |
| Paperbridge API | `apps/api/*`, `docs/security.md` | No public auth; localhost bind; MCP localhost Host/Origin only. |

## Classification reminder

- **Documented:** MCP, exe.dev, Pi adapter, SDK docs/types as cited.
- **Implemented:** unauthenticated localhost REST/MCP with loopback MCP guards.
- **Host-tested / physically verified:** not claimed for any exe.dev deployment
  path in this document.

No runtime code was changed by this research.
