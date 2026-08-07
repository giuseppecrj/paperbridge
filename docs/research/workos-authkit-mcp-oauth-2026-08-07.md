# WorkOS AuthKit for Paperbridge standard MCP OAuth

**Research date:** 2026-08-07  
**Scope:** Whether WorkOS AuthKit can be the OAuth authorization server (AS) for
Paperbridge's Streamable HTTP MCP endpoint.

## Evidence classification

- **Documented:** WorkOS and official MCP specification facts cited below.
- **Design inference:** The Paperbridge architecture and conclusion combine those
  documented facts with the required protocol roles. They are not an implementation
  or a WorkOS support commitment.
- **Not claimed:** host test, deployment, pricing, SLA, or physical verification.

## Conclusion

**Yes, conditionally.** WorkOS documents AuthKit as a spec-compatible OAuth AS
for an application-built MCP resource server, not only as an upstream IdP.
AuthKit supplies the OAuth authorization, token, registration, discovery, and
JWKS surfaces; Paperbridge must still be the resource server (RS): publish its
protected-resource metadata, issue the bearer challenge, validate AuthKit JWTs
for Paperbridge's audience, and make Paperbridge Owner/Sender/Invite decisions.
[W-MCP] [MCP]

This supports third-party MCP clients with no existing relationship when the
required WorkOS Connect settings are enabled. Current MCP prefers Client ID
Metadata Documents (CIMD); WorkOS documents Dynamic Client Registration (DCR)
for backwards compatibility. Do not describe support as unconditional for every
client: a client must implement a supported registration path and Paperbridge
must configure the corresponding WorkOS option. [W-MCP] [MCP]

## 1. AuthKit authentication and session model

- AuthKit's hosted UI handles sign-up/sign-in, password reset, email
  verification, enterprise SSO routing, and MFA. The application redirects the
  user to AuthKit; after WorkOS authentication, it exchanges an authorization
  code for an authenticated User object and manages the application session.
  This can authenticate a Paperbridge Owner. [W-HOSTED]
- A successful AuthKit authentication response includes access and refresh
  tokens. WorkOS says to validate the JWT access token on every backend request,
  store it in a secure browser cookie, retain the refresh token securely, and
  replace a rotated refresh token. Session maximum length, access-token duration,
  and inactivity timeout are dashboard configuration. [W-SESSION]
- This browser/application session is distinct from an MCP client's OAuth token.
  For MCP, AuthKit's Connect OAuth flow authenticates the user and issues the
  bearer token to the MCP client. [W-MCP] **Design inference.**

## 2. AuthKit as MCP authorization server

| Capability | Official WorkOS evidence | Result |
| --- | --- | --- |
| AS role | AuthKit is documented as the spec-compatible OAuth AS; the application MCP server is the RS. | **Yes**. [W-MCP] |
| Authorization/token endpoints | AS metadata documents `/oauth2/authorize` and `/oauth2/token`; it advertises authorization-code and refresh-token grants plus S256 PKCE. | **Yes**. [W-MCP] |
| Discovery | AuthKit serves OAuth AS metadata at `https://<authkit-domain>/.well-known/oauth-authorization-server`. | **Yes** (RFC 8414 route). [W-MCP] |
| JWKS | WorkOS documents JWT verification against `https://<authkit-domain>/oauth2/jwks`, with issuer and audience validation. | **Yes**. [W-MCP] [W-CONNECT] |
| Client registration | WorkOS documents CIMD as the current MCP route (dashboard enablement required) and DCR as an enableable compatibility route. Its metadata example contains `/oauth2/register`. | **Yes, configure it**. [W-MCP] |
| Resource/audience | Configure the exact MCP URL as a valid Resource Indicator. The MCP client sends `resource`; WorkOS issues `aud` matching that resource. | **Yes, after configuration**. [W-MCP] |

The `resource` is client-requested, not client-issued authority: WorkOS validates
it against configured Resource Indicators before issuing the token. Without a
configured indicator, WorkOS documents that it ignores `resource` and uses the
environment client ID as `aud`; that is not the desired Paperbridge MCP audience.
Clients that omit `resource` need a configured default Resource Indicator.
[W-MCP]

## 3. Narrow comparison with current MCP authorization requirements

| MCP requirement | AuthKit/Paperbridge division |
| --- | --- |
| HTTP authorization is optional; when supported it should conform. | Implement the full RS path, or keep Paperbridge private and do not claim MCP OAuth. [MCP] |
| AS implements OAuth 2.1 and offers AS metadata or OIDC discovery. | AuthKit documents OAuth AS metadata, authorization/token endpoints, S256 PKCE, and Connect OAuth. [W-MCP] [MCP] |
| AS/client should support CIMD; DCR is optional compatibility. | Enable WorkOS CIMD. Enable DCR only for clients that need it. [W-MCP] [MCP] |
| RS must expose Protected Resource Metadata (PRM); client uses it to find the AS. | Paperbridge must expose `/.well-known/oauth-protected-resource` with its canonical resource URL and AuthKit in `authorization_servers`. [W-MCP] [MCP] |
| Client sends `resource` to authorization and token endpoints; RS validates intended audience. | Configure the same canonical Paperbridge `/mcp` URL in WorkOS and verify JWT issuer and `aud` before every MCP request. [W-MCP] [MCP] |
| Bearer token is in every HTTP request; RS must not pass it downstream. | Gate `/mcp` before the MCP handler. Never send that token to MQTT or the Device. [MCP] **Design inference.** |

## 4. Recommended role boundary

```text
Owner -> AuthKit hosted UI / configured IdP -> AuthKit OAuth AS
MCP client -> AuthKit authorization + consent -> AuthKit access token (aud = Paperbridge /mcp)
MCP client -- Authorization: Bearer --> Paperbridge MCP RS -> MQTT -> Device
                                      |-- JWT issuer/signature/expiry/aud check
                                      `-- Owner/Sender/Invite authorization
```

1. Configure an AuthKit domain and WorkOS Connect; enable CIMD, and DCR only if
   compatibility requires it. Register the canonical public MCP URL as a
   Resource Indicator (and default it only for clients that omit `resource`).
   [W-MCP]
2. Add Paperbridge PRM and a 401 `WWW-Authenticate` challenge that names it.
   PRM identifies the same canonical resource and the AuthKit AS. [W-MCP] [MCP]
3. Before handling each `/mcp` request, verify the AuthKit JWT using its JWKS,
   issuer, expiry, and Paperbridge MCP URL as audience. [W-MCP] [W-CONNECT]
4. Map verified `sub` to Paperbridge identities, then enforce the Owner's
   directional Invite policy for the target physical inbox. AuthKit identifies
   and authenticates the actor; Paperbridge remains the authority for its
   physical-inbox authorization model. **Design inference.**
5. Keep broker credentials server-side and do not forward the MCP access token.
   [MCP] **Design inference.**

## Operational and pricing implications

- Directly documented setup work: dashboard enablement of CIMD, optional DCR,
  and Resource Indicators/defaults; public OAuth applications use PKCE. [W-MCP]
  [W-CONNECT]
- No pricing, quota, SLA, or production-operability claim is made here because
  no such WorkOS statement was needed or verified for this question.

## Source register

| ID | Official source | Recorded fact |
| --- | --- | --- |
| [W-HOSTED] | <https://workos.com/docs/authkit/hosted-ui> | Hosted sign-in flow, identity-provider support, code exchange, and User object. |
| [W-SESSION] | <https://workos.com/docs/authkit/sessions> | Access/refresh tokens, JWT validation, secure storage, refresh, and session configuration. |
| [W-MCP] | <https://workos.com/docs/authkit/mcp> | AuthKit AS role; endpoints; CIMD/DCR; resource indicators; JWT/PRM integration. |
| [W-CONNECT] | <https://workos.com/docs/authkit/connect/oauth> | OAuth authorization-code flow, public-client PKCE, JWKS verification, and user/organization claims. |
| [MCP] | <https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization> | Current MCP OAuth roles, PRM/discovery, CIMD/DCR, resource indicators, token validation, and bearer rules. |

No runtime code or existing document was changed by this research.
