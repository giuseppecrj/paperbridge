# exe.dev OIDC/OAuth integration for Paperbridge MCP

**Research date:** 2026-08-07  
**Scope:** Whether exe.dev can be Paperbridge MCP's OAuth/OIDC authorization
server, or can remain the HTTPS proxy when Paperbridge uses another one.

## Evidence classification

This note records **documented** exe.dev and MCP facts, plus the responses from
exe.dev's public discovery URLs on the research date. It is not an exe.dev
support statement, deployment, host test, or physical verification. Absence
from documentation or discovery is an **unknown**, not proof that an
undocumented endpoint can never exist.

## Direct conclusion

**exe.dev does not document a usable OAuth/OIDC authorization-server integration
for Paperbridge MCP.** “Login with exe” is a browser/proxy identity feature:
it redirects to an exe.dev login page, uses a domain cookie, and injects identity
headers into the proxied request. It is not documented as an OAuth authorization
code or token service. [login]

exe.dev does publish a minimal OIDC discovery document and JWKS. On 2026-08-07,
the discovery response identifies an issuer and `jwks_uri`, supports signed
`id_token` responses, but does not advertise an `authorization_endpoint`,
`token_endpoint`, registration endpoint, grants, or scopes. This is insufficient
for Paperbridge to use exe.dev as the MCP OAuth authorization server. [oidc]
[jwks]

Use the private exe.dev proxy as infrastructure access control for the current
one-Owner service. Do not describe it as MCP OAuth. For standard MCP OAuth,
Paperbridge must implement the resource-server side and use an external
authorization server, or operate its own one later.

## Findings

### 1. “Login with exe” is proxy login and identity headers

The documented flow is:

- `https://<vm>.exe.xyz/__exe.dev/login?redirect=…` redirects a browser to log
  in and returns it to the requested path.
- Logout removes the cookie for that domain.
- The proxy adds `X-ExeDev-UserID` and `X-ExeDev-Email` for authenticated
  requests. Public proxy requests have neither header when unauthenticated.

The same documentation tells an application developer to implement its own
authorization with these headers; it does not publish an OAuth/OIDC client flow,
access-token issuance, or bearer-token validation contract for the application.
[login]

**Answer:** Login with exe is documented as browser/proxy authentication and an
identity-header feature, not as a documented OIDC provider suitable for MCP.

### 2. Discovery and OAuth endpoint inventory

| Capability | Official evidence | Result for MCP OAuth |
| --- | --- | --- |
| OIDC discovery | `/.well-known/openid-configuration` returned JSON with issuer, RS256 ID-token signing support, `jwks_uri`, `response_types_supported: ["id_token"]`, and public subjects. | **Exists, but minimal.** |
| JWKS | The advertised `/.oidc/jwks.json` returned an RSA signing key set. | **Exists.** This can verify a compatible signed assertion only when its issuance and claims are defined. |
| Authorization endpoint | No `authorization_endpoint` appears in the discovery response. The Login URL is the only documented browser-auth URL. | **Not documented or advertised.** |
| Token endpoint | No `token_endpoint` appears in discovery. exe.dev documents SSH-generated bearer tokens for its API/proxy, not an OAuth token endpoint. | **Not documented or advertised.** |
| Dynamic client registration | No registration endpoint appears in discovery or the relevant exe.dev docs. | **Not documented or advertised.** |
| Token exchange | No token-exchange endpoint or grant is documented or advertised. | **Not documented or advertised.** |

Direct requests on the research date returned 404 for exe.dev's standard OAuth
AS metadata path (`/.well-known/oauth-authorization-server`) and common paths
`/oauth/authorize`, `/oauth/token`, and `/oauth/register`. These observations
only narrow the documented/public surface; they do not establish a support
commitment about undisclosed paths. [oauth-as-metadata] [oauth-authorize]
[oauth-token] [oauth-register]

### 3. exe.dev proxy credentials and headers are not MCP OAuth AS/RS

For non-browser access, exe.dev documents VM-scoped bearer tokens sent on
`X-Exedev-Authorization`; the proxy consumes and strips that header. It then
passes identity headers and, when present, a signed token `ctx` value in
`X-ExeDev-Token-Ctx` to the VM. [vm-tokens] The HTTPS API documents those tokens
as SSH-generated, signed exe.dev API/proxy credentials, with expiry and command
permissions—not OAuth access tokens issued for a Paperbridge resource. [https-api]

Therefore:

- They **can** gate a private proxy and provide proxy-authenticated context to a
  Paperbridge application.
- They **cannot by themselves** supply MCP OAuth authorization-server discovery,
  authorization, client registration, or token exchange.
- They do **not** make Paperbridge an MCP OAuth resource server. A protected MCP
  server must publish Protected Resource Metadata, validate access tokens for
  its own resource audience, and point clients to an authorization server.
  [mcp-auth]

Paperbridge may use trusted exe.dev headers for a deliberately private,
non-OAuth edge policy only if its Node service remains reachable solely through
the proxy (the existing loopback bind is appropriate). That is infrastructure
access, not a Paperbridge Sender identity, Invite, or OAuth authorization model.

### 4. External OIDC IdP with exe.dev retained as proxy

MCP permits the authorization server to be separate from the MCP resource
server. Its current authorization specification requires MCP protected-resource
metadata and authorization-server metadata or OIDC discovery; the authorization
server is responsible for user interaction and issuing access tokens. [mcp-auth]

A standards-compatible future shape is:

```text
MCP client -- OAuth bearer --> exe.dev HTTPS proxy --> Paperbridge MCP resource server
                         \                        /
                          ---- external OIDC/OAuth IdP
```

- Keep exe.dev private and use its browser login or VM token as the **edge**
  control.
- Configure Paperbridge `/mcp` as the resource server: publish its protected
  resource metadata, direct discovery to the external IdP, and validate bearer
  tokens, issuer, signature, expiry, and Paperbridge audience before the MCP
  handler.
- Keep MQTT credentials server-side. Do not forward an MCP access token to MQTT
  or treat it as a Device credential.

This is not an exe.dev proxy OIDC integration. No official exe.dev source found
that configures an external IdP at the proxy or maps its claims into the
`X-ExeDev-*` headers. It is a Paperbridge application integration behind a
separate proxy boundary.

**Important unknown before implementation:** exe.dev documents deprecated
`Authorization: Bearer` proxy-token authentication and preferred, stripped
`X-Exedev-Authorization`, but does not specify the behavior when an external
OAuth `Authorization: Bearer` header and proxy authentication are both present.
Confirm that forwarding behavior with exe.dev support or a no-output staging
request before selecting this layout.

## Implications for Paperbridge

1. Keep the current private-proxy `X-Exedev-Authorization` model for the
   one-Owner MCP service. It is the smallest documented non-browser mechanism.
2. Do not add exe.dev discovery/JWKS as Paperbridge MCP OAuth configuration and
   do not point MCP clients at the exe.dev Login URL.
3. When public access, independent Senders, or standards-based MCP OAuth is
   required, select an external IdP and implement Paperbridge as an OAuth
   resource server. Preserve the proxy as a separate access layer if desired.
4. Before that work, resolve the two operational unknowns: combined proxy/app
   `Authorization` handling and a proxy-only trust proof for injected headers.

## Source register

All sources accessed 2026-08-07.

| ID | Official source | Recorded fact |
| --- | --- | --- |
| [login] | <https://exe.dev/docs/login-with-exe> | Cookie login/logout and injected user/email headers for proxied requests. |
| [vm-tokens] | <https://exe.dev/docs/https-tokens-for-vms> | VM tokens, preferred stripped `X-Exedev-Authorization`, and headers delivered to the VM. |
| [https-api] | <https://exe.dev/docs/https-api> | SSH-generated signed bearer tokens, expiry, permissions, and `ctx`. |
| [proxy] | <https://exe.dev/docs/proxy> | Private HTTP proxy and forwarded-request boundary. |
| [oidc] | <https://exe.dev/.well-known/openid-configuration> | Public discovery response observed on the research date. |
| [jwks] | <https://exe.dev/.oidc/jwks.json> | JWKS advertised by the discovery response. |
| [oauth-as-metadata] | <https://exe.dev/.well-known/oauth-authorization-server> | 404 observed on the research date. |
| [oauth-authorize] | <https://exe.dev/oauth/authorize> | 404 observed on the research date. |
| [oauth-token] | <https://exe.dev/oauth/token> | 404 observed on the research date. |
| [oauth-register] | <https://exe.dev/oauth/register> | 404 observed on the research date. |
| [mcp-auth] | <https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization> | Current official MCP OAuth roles, discovery, resource metadata, token validation, and audience requirements. |

No runtime code or existing document was changed by this research.
