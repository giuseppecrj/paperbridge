# MCP OAuth primary-source notes

**Research date:** 2026-08-15  
**Purpose:** Source-backed notes for the Paperbridge MCP OAuth migration proposal.  
**Evidence boundary:** Documentation and source inspection only. No secrets,
deployment changes, proxy visibility changes, or physical-device actions.

## Current MCP authorization requirements

- [MCP 2026-07-28 authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md)
  says authorization is optional; HTTP implementations that support it should
  conform. A protected MCP server is an OAuth resource server.
- The resource server **MUST** implement Protected Resource Metadata (PRM,
  [RFC 9728](https://www.rfc-editor.org/rfc/rfc9728)); MCP clients **MUST** use
  PRM for authorization-server discovery.
- The authorization server **MUST** provide RFC 8414 OAuth Authorization Server
  Metadata or OIDC Discovery; clients **MUST** support both discovery mechanisms.
- Clients **MUST** send the RFC 8707 `resource` parameter in both authorization
  and token requests. The resource is an absolute canonical URI without a
  fragment and should identify the specific MCP resource.
- The MCP bearer token is sent in `Authorization: Bearer ...` on every HTTP
  request. Tokens **MUST NOT** be put in query strings.
- The resource server **MUST** validate the token for its own audience and
  **MUST NOT** accept or pass through a token intended for another service.
- Missing/invalid authorization uses HTTP 401; insufficient scope uses HTTP 403.
  A 401 challenge uses `WWW-Authenticate`, including the PRM URL through the
  `resource_metadata` parameter. Servers should include the required scope.
- AS endpoints must use HTTPS. Redirect URIs must be HTTPS or localhost.
- PKCE is required for public clients. Clients capable of PKCE use `S256`.
- The current specification requires clients to obtain a client ID through
  pre-registration, CIMD, or DCR. The priority is pre-registration, then CIMD
  when `client_id_metadata_document_supported` is advertised, then DCR fallback.
  The 2026-07-28 specification deprecates DCR for new deployments but permits it
  for backward compatibility.

Primary pages:

- [Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md)
- [Client registration](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/client-registration.md)
- [Authorization-server discovery](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/authorization-server-discovery.md)
- [Changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog.md)
- [Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md)

## Relevant RFC facts

- [RFC 9728](https://www.rfc-editor.org/rfc/rfc9728), April 2025: PRM uses a
  required exact `resource` value, may list authorization servers, is retrieved
  from the appropriate `.well-known` URI, and can be advertised through
  `WWW-Authenticate: ... resource_metadata=...`.
- [RFC 8414](https://www.rfc-editor.org/rfc/rfc8414), June 2018: AS metadata
  requires an HTTPS issuer with no query or fragment; clients must validate the
  metadata issuer exactly against the issuer used for discovery.
- [RFC 8707](https://www.rfc-editor.org/rfc/rfc8707), February 2020: resource
  indicators are absolute URIs without fragments; the AS should restrict the
  resulting access token to the requested resource/audience.
- [RFC 7636](https://www.rfc-editor.org/rfc/rfc7636), September 2015: a PKCE
  verifier is 43–128 characters, `S256` is mandatory to implement, and the token
  endpoint verifies the code challenge binding.
- [RFC 6750](https://www.rfc-editor.org/rfc/rfc6750), October 2012: bearer
  authorization is carried in the Authorization header; resource servers support
  the header method and use `WWW-Authenticate` for unauthenticated challenges,
  `401 invalid_token`, and `403 insufficient_scope`.
- [OAuth Client ID Metadata Document draft](https://datatracker.ietf.org/doc/draft-ietf-oauth-client-id-metadata-document/)
  is an active Internet-Draft, not an RFC. The -02 draft was published
  2026-07-06 and expires 2027-01-07. MCP pages still link the -00 draft, so the
  provider/client implementation must be checked against the current MCP
  revision and draft interoperability.
- [RFC 7591](https://www.rfc-editor.org/rfc/rfc7591) remains a Standards Track
  DCR protocol, but current MCP deprecates it as the preferred new registration
  mechanism.

## Official TypeScript SDK

- [SDK authorization serving guide](https://ts.sdk.modelcontextprotocol.io/v2/serving/authorization.md)
  documents `requireBearerAuth`, the `401`/`WWW-Authenticate` behavior, 403
  insufficient-scope behavior, and `mcpAuthMetadataRouter` for PRM and AS
  metadata.
- [SDK OAuth examples](https://github.com/modelcontextprotocol/typescript-sdk/tree/main/examples/oauth)
  include authorization-code resource-server/authorization-server examples,
  browser/headless flows, and token validation.
- [SDK OAuth client guide](https://ts.sdk.modelcontextprotocol.io/v2/clients/oauth.md),
  [machine authentication](https://ts.sdk.modelcontextprotocol.io/v2/clients/machine-auth.md),
  [bearer-auth example](https://github.com/modelcontextprotocol/typescript-sdk/tree/main/examples/bearer-auth),
  and [web bearer-auth example](https://github.com/modelcontextprotocol/typescript-sdk/tree/main/examples/bearer-auth-web)
  are relevant implementation references.
- The repository itself pins `@modelcontextprotocol/server`, `@modelcontextprotocol/node`,
  and `@modelcontextprotocol/client` at `2.0.0`; do not assume the `main` branch
  examples are API-compatible without checking the pinned package.
- The SDK handler does not itself verify bearer tokens; verification must occur
  before the handler and be passed through as auth context.

## exe.dev primary-source facts

- [Proxy](https://exe.dev/docs/proxy): exe.dev terminates TLS at the proxy,
  uses `vmname.exe.xyz` hostnames, defaults shares to private, documents
  `share port` and public/private share controls, and supplies `X-Forwarded-*`
  headers.
- [Sharing](https://exe.dev/docs/sharing): public, email-share, and share-link
  modes have different access semantics.
- [HTTPS tokens for VMs](https://exe.dev/docs/https-tokens-for-vms): the
  preferred non-browser header is `X-Exedev-Authorization: Bearer ...`; the
  proxy consumes/strips it. `Authorization: Bearer` is deprecated for this
  purpose. The proxy supplies identity and optional context headers to the VM.
- [HTTPS API](https://exe.dev/docs/https-api): tokens can include `exp`, `nbf`,
  `cmds`, and `ctx`; an explicit `exp` is strongly recommended and the default
  expiry is distant. Invalid or expired tokens receive 401. The docs do not
  provide replay protection for these VM credentials.
- [Login with exe](https://exe.dev/docs/login-with-exe): browser login uses a
  cookie and exposes `X-ExeDev-UserID` and `X-ExeDev-Email` to the proxied
  application. It is not documented as an OAuth authorization-code/token
  service.

The documentation does not establish a contractual guarantee that a client can
never supply a conflicting `X-ExeDev-*` header or that the proxy always strips or
overwrites every such field. Obtain confirmation from exe.dev and test through
a staging public share before using these headers as an upstream identity.

## Client compatibility evidence

### ChatGPT and OpenAI

- [ChatGPT MCP extension documentation](https://learn.chatgpt.com/docs/extend/mcp.md)
  describes Streamable HTTP, bearer/OAuth configuration, and shared ChatGPT,
  Codex, and IDE MCP configuration surfaces.
- [OpenAI plugin authentication](https://developers.openai.com/plugins/build/auth.md)
  documents OAuth 2.1 expectations, CIMD/DCR/pre-registration, PKCE/S256,
  resource echoing, the ChatGPT callback shape, bearer tokens, and the absence
  of `client_credentials`/custom API-key authentication for that flow.
- [OpenAI ChatGPT deployment](https://developers.openai.com/plugins/deploy/connect-chatgpt.md)
  requires public HTTPS/Streamable HTTP or the Secure MCP Tunnel for developer
  mode.
- [OpenAI remote MCP tools](https://platform.openai.com/docs/guides/tools-connectors-mcp.md)
  documents remote Streamable HTTP or HTTP/SSE, `server_url`, and authorization
  tokens.
- Account, plan, and product-surface availability must be tested in the actual
  ChatGPT tenant; documentation alone is not an acceptance result.

### Claude

- [Anthropic MCP connector](https://platform.claude.com/docs/en/agents-and-tools/mcp-connector.md)
  documents direct remote MCP from the Messages API, public HTTPS, Streamable
  HTTP and SSE, and OAuth bearer use with a pre-obtained `authorization_token`.
  The client handles OAuth/refresh outside the direct connector call. The
  connector is tools-only and product/API beta details may vary.

### Cursor

- [Cursor MCP](https://cursor.com/docs/mcp.md) documents stdio, SSE, and
  Streamable HTTP, remote OAuth, static OAuth client credentials, fixed OAuth
  callback URLs, and arbitrary headers/environment interpolation.

### VS Code / GitHub Copilot

- [VS Code MCP servers](https://code.visualstudio.com/docs/copilot/chat/mcp-servers)
  documents remote HTTP MCP configuration and the current `mcp.json` shape.
  The page does not document OAuth, CIMD, or DCR behavior. Mark those behaviors
  unknown until tested in the target VS Code/Copilot build.

### Codex

- [OpenAI MCP extension documentation](https://learn.chatgpt.com/docs/extend/mcp.md)
  documents Streamable HTTP, bearer/OAuth, `url`, bearer environment settings,
  static headers, and CLI login.
- [Codex client registration source](https://github.com/openai/codex/blob/main/codex-rs/rmcp-client/src/oauth_client_registration.rs)
  shows current Codex behavior using CIMD when advertised and DCR fallback,
  including callback client metadata, PKCE, resource, and issuer-validation
  tests. This is source evidence for the referenced revision, not a guarantee
  for every released Codex binary.

### MCP Inspector

- [Inspector documentation](https://modelcontextprotocol.io/docs/tools/inspector.md)
  and [Inspector authorization](https://modelcontextprotocol.io/docs/2026-07-28/tools/inspector/authorization.md)
  document the web/CLI/TUI Inspector package, `401` PRM discovery,
  pre-registration/CIMD/DCR, browser callback, persisted tokens, and reauth or
  step-up flows.
- [Inspector repository](https://github.com/modelcontextprotocol/inspector)
  is the source for current package/release details. The observed current main
  line was package `2.2.0`; pin the version used for acceptance.

## Managed-provider note

- [WorkOS MCP AuthKit](https://workos.com/docs/authkit/mcp) explicitly documents
  MCP PRM, resource indicators, audience claims, CIMD enablement, optional DCR
  compatibility, and JWKS token verification.
- [WorkOS Standalone Connect](https://workos.com/docs/authkit/connect/standalone)
  supports an existing application login: AuthKit redirects to a configured
  Login URI with a temporary `external_auth_id`; the application authenticates
  the user and calls the AuthKit completion API; AuthKit then handles consent,
  code issuance, and token exchange.
- [WorkOS OAuth](https://workos.com/docs/authkit/connect/oauth) documents public
  applications with PKCE, JWKS verification, and optional introspection.
- [Auth0 PKCE](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce),
  [refresh rotation](https://auth0.com/docs/secure/tokens/refresh-tokens/refresh-token-rotation),
  and [DCR](https://auth0.com/docs/get-started/applications/dynamic-client-registration)
  establish a generic managed fallback, but generic OIDC capability alone does
  not prove MCP PRM/resource-indicator interoperability.

## Uncertainties that remain architectural gates

1. exe.dev header overwrite/stripping and public-share Login with exe behavior.
2. WorkOS tenant configuration, subject mapping, resource-indicator exactness,
   token lifetimes, revocation/introspection semantics, cost, and data handling.
3. Exact OAuth behavior of the target versions of ChatGPT, Claude, Cursor, VS
   Code/Copilot, and Codex.
4. Whether the pinned MCP SDK `2.0.0` should be upgraded before using the v2
   authorization helper APIs.

No Paperbridge runtime, proxy, secret, or hardware state was changed while
creating these notes.
