# API schema design for Paperbridge and Ephemera

Research performed 2026-08-15 against current official OpenAPI, JSON Schema,
HTTP, MCP, and JSON:API specifications plus the implemented Paperbridge REST,
MCP, MQTT, protocol, firmware, and test paths. This note recommends a contract
shape; it does not implement or approve an API migration, deployment, or
physical operation.

## Question

Paperbridge currently accepts a raw `print-job.v1` at `POST /api/jobs`, while
MCP accepts only receipt `content` and creates the job identity server-side.
Ephemera adds application concerns such as Publication Consent and a separate
Publication Outcome. What standard contract approach can express those concerns
without leaking them into MQTT or firmware, while remaining portable and easy to
evolve?

## Recommendation

Use this standards stack:

1. **JSON Schema Draft 2020-12 is the canonical payload-contract format.**
2. **OpenAPI 3.1.2 describes the HTTP interface** and references the standalone
   JSON Schemas. OpenAPI 3.2.0 is the current release, but 3.1.2 already supports
   the needed Draft 2020-12 model and is the conservative first tooling profile.
   Reconsider 3.2.0 when the selected validator, documentation renderer, and any
   code generator pass repository acceptance tests with it.
3. **RFC 9457 Problem Details describes HTTP-level failures.**
4. **Ordinary JSON represents successful domain outcomes.** Do not adopt a
   generic success envelope or JSON:API.
5. **Opaque cursor pagination plus RFC 8288 `Link` headers** describes receipt
   collection traversal. Cursor field names are a Paperbridge convention, not
   an Internet standard.
6. **Do not claim HTTP idempotency yet.** `job_id` continues to correlate domain
   work, but the expired IETF `Idempotency-Key` Internet-Draft is not an RFC and
   current one-boot MQTT duplicate suppression is not durable HTTP idempotency.

The key seam is:

```text
REST or MCP application contract
              |
              v
      application adapter
              |
              v
        print-job.v1
              |
              v
 MQTT -> Device -> job-result.v1
```

The application contract may change. The Device contracts do not.

## Why these standards

### JSON Schema Draft 2020-12

Paperbridge already uses Draft 2020-12 with absolute `$id` values,
`$defs`, closed objects, and Ajv validation in:

- `packages/protocol/schemas/print-job.v1.schema.json`;
- `packages/protocol/schemas/job-result.v1.schema.json`; and
- `packages/protocol/src/index.ts`.

Draft 2020-12 defines schema identities and references, reusable definitions,
logical composition, and the distinction between applicator evaluation and
unevaluated properties. Use direct `$ref` reuse and small named schemas. Use
`oneOf` only when exactly one alternative may validate. Do not try to extend the
closed `print-job.v1` object with `allOf`; define an outer application schema
instead.

Source: [JSON Schema Core Draft 2020-12, especially §§8.2, 10.2, and
11.3](https://json-schema.org/draft/2020-12/json-schema-core).

### OpenAPI

OpenAPI is a language-independent description of an HTTP interface. It should
describe routes, parameters, bodies, responses, security, and reusable schemas;
it should not become a second source of truth for the Device payloads.
Standalone Draft 2020-12 schemas can be referenced from the OpenAPI description.

OpenAPI 3.2.0 is the current specification. OpenAPI 3.1.2 remains a stable
profile with the JSON Schema capabilities this API needs. Choosing 3.1.2 first
is an implementation compatibility decision, not a claim that it is the latest
version.

Sources:

- [OpenAPI Specification 3.2.0](https://spec.openapis.org/oas/v3.2.0.html)
- [OpenAPI Specification 3.1.2 Schema Object](https://spec.openapis.org/oas/v3.1.2.html#schema-object)

### MCP

Current MCP tools define `inputSchema` and optional `outputSchema` as JSON
Schema and default to Draft 2020-12. Paperbridge can therefore reuse application
schema fragments across REST and MCP without forcing their transport envelopes
to be identical. MCP keeps its own JSON-RPC/protocol errors; successful tool
results can expose the same structured Submission Outcome as REST.

Source: [MCP JSON Schema usage and tool schemas,
2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic#json-schema-usage).

### HTTP errors

RFC 9457 defines `application/problem+json` for machine-readable HTTP failures
and supersedes RFC 7807. Use stable Paperbridge-owned `type` URIs, safe titles,
HTTP status, and an `errors` extension with JSON Pointers for validation issues.
Do not expose stack traces, broker internals, credentials, or printer content in
Problem Details.

A valid accepted submission has a domain outcome, not necessarily an HTTP
problem. In particular, a separate failed Publication Outcome must not overwrite
a successful `delivered_to_printer` Job Result or make physical delivery appear
retryable. Whether all accepted delivery outcomes should return HTTP 200 is a
separate product-interface decision to settle in the specification.

Sources:

- [RFC 9457 §§3–4](https://www.rfc-editor.org/rfc/rfc9457.html#section-3)
- [RFC 9110 response semantics](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3)

## Recommended contract family

Keep these Device contracts unchanged:

- `print-job.v1` — printable semantic meaning and Device identity;
- `job-result.v1` — terminal Device report;
- MQTT topics, QoS 1, non-retained behavior, and payload limits;
- firmware validation and honest `delivered_to_printer` vocabulary.

Add application-owned schemas:

### `job-submission.v1`

The subsequent POC design selected a closed application command containing
receipt content and an optional publication choice. The Host, rather than the
caller, creates the Semantic Print Job identity, selects the configured Device,
and records creation time. Do not add an unrestricted `metadata` object.

Approved direction:

```json
{
  "schema_version": "1",
  "kind": "job_submission",
  "content": {
    "kind": "receipt",
    "blocks": [{ "type": "text", "text": "Hello" }]
  },
  "publish": true
}
```

The application adapter validates the submission, creates the job, performs
Host-side image preparation, validates the prepared job again, and sends only
`print-job.v1` to MQTT.

### `submission-outcome.v1`

A closed application result containing:

- the unchanged Job Result or the application's honest Unknown Delivery Result;
- a separate Publication Outcome such as not requested, not eligible, published,
  or failed; and
- a public receipt URL only when publication succeeds.

A Publication failure never changes the Job Result and never authorizes another
Semantic Print Job.

### `digital-receipt.v1`

A public resource derived from the canonical prepared schema-valid job. It
contains the public slug, publication time, exact `delivered_to_printer`
vocabulary, receipt content, and its schema version. It excludes `job_id`,
`device_id`, consent evidence, internal errors, and Recipient identity.

The schema should reference the authoritative individual text, QR, raster, feed,
rule, and cut definitions rather than duplicate them. It must not reference the
broader source-job block union because that union also permits the API-only
source `image` block.

### Receipt collection

`GET /api/receipts` returns a bounded newest-first page of
`digital-receipt.v1` values and an opaque `next_cursor`. It should also send an
RFC 8288 `Link` header with `rel="next"` when another page exists.
`GET /api/receipts/{slug}` returns one Digital Receipt.

Cursor tokens must remain opaque and URL-safe. Stable ordering must include a
unique tie-breaker. Do not expose row offsets or database identifiers as the
cursor contract.

Sources:

- [RFC 8288 Web Linking](https://www.rfc-editor.org/rfc/rfc8288.html)
- [IANA Link Relation registry](https://www.iana.org/assignments/link-relations/link-relations.xhtml)
- [Google AIP-158](https://google.aip.dev/158) as a first-party convention for
  bounded pages and opaque tokens, not an Internet standard

## REST migration

The clean implementation seam is `apps/api/src/job-service.ts`, before
`parsePrintJob`, image preparation, and MQTT encoding.

Because the existing API is private and pre-release, replace the raw
`POST /api/jobs` request once with the chosen `job-submission.v1` shape. Reject
ambiguous legacy bodies rather than keeping permanent union parsing. Update all
private callers, fixtures, tests, examples, and documentation in the same
migration.

The current blast radius includes:

- `apps/api/src/api-server.ts`;
- `apps/api/src/job-service.ts`;
- `apps/api/src/mcp-server.ts`;
- API unit, integration, production-bundle, and container-acceptance tests;
- protocol fixtures consumed by API tests;
- `apps/api/README.md`, `docs/protocol.md`, `docs/private-cloud-access.md`,
  `docs/architecture.md`, and root `README.md`; and
- the Mosquitto/firmware end-to-end Host tests.

Do not change the firmware validator merely to accommodate the REST wrapper.
Firmware must continue to receive and validate the extracted prepared
`print-job.v1` only.

## Success and failure semantics

For a synchronous command that completes during the request, HTTP 200 with a
Submission Outcome is the natural success representation. HTTP 201 plus
`Location` is appropriate only if the API creates a durable Job resource. HTTP
202 is appropriate only if processing continues asynchronously and the API
provides a status resource.

Use Problem Details for failures before a valid submission outcome exists, such
as malformed JSON, unsupported media type, schema failure, body limits,
unauthenticated access, unavailable submission service, or draining before
acceptance.

Do not invent a global wrapper such as `{ "data": ..., "meta": ... }` around
every success. The Submission Outcome envelope is justified because this one
command has two independent domain outcomes.

## Idempotency

The IETF `Idempotency-Key` work remained an expired Internet-Draft at the
research date, not an RFC. Do not advertise compliance with a standard that does
not exist. A future durable HTTP idempotency design must explicitly define:

- key scope and authenticated principal;
- retention period;
- request fingerprinting and conflict behavior;
- concurrent in-flight behavior;
- replay of the original complete outcome; and
- interaction with `job_id` and durable Device execution receipts.

For Ephemera publication, `job_id` can still provide domain-level uniqueness:
identical repeated Publication Attempts return the existing permalink;
conflicting content under the same `job_id` is rejected; a withdrawal tombstone
blocks republication. This is not a claim that `POST /api/jobs` is durably
idempotent.

Source: [IETF HTTPAPI Idempotency-Key Internet-Draft
revision 07](https://www.ietf.org/archive/id/draft-ietf-httpapi-idempotency-key-header-07.html).

## Versioning and deprecation

There is no universal HTTP API-versioning standard. Make compatible additions
in place and introduce a new major only for breaking changes. Keep payload
schemas explicitly versioned with stable `$id` values. Do not add `/v1` to every
route solely because versioning might be needed later.

When a public HTTP version is eventually deprecated, use the standardized
`Deprecation` response header, optionally `Sunset`, and a `rel="deprecation"`
documentation link.

Source: [RFC 9745 Deprecation HTTP Response
Header](https://www.rfc-editor.org/rfc/rfc9745.html).

## Why not JSON:API

JSON:API 1.1 mandates `application/vnd.api+json` and its own document,
resource, relationship, error, pagination, and content-negotiation rules. Those
rules provide little leverage for this small command-oriented API, would replace
rather than complement RFC 9457 errors, and do not map naturally to MCP tool
schemas and structured results.

Use ordinary `application/json`, focused domain schemas, OpenAPI, RFC 9457, and
RFC 8288 instead.

Source: [JSON:API 1.1](https://jsonapi.org/format/1.1/).

## Type safety and source-of-truth discipline

The current TypeScript `PrintJob` and `JobResult` types in
`packages/protocol/src/index.ts` are handwritten duplicates of the JSON Schemas.
That creates drift risk. The implementation specification should evaluate either
schema-derived TypeScript types or a build/test check that proves the handwritten
types and schemas agree. Do not choose a new schema library before testing its
Draft 2020-12, OpenAPI, ESM, Bun, Node, and MCP behavior in this repository.

OpenAPI should reference or embed the canonical JSON Schemas. Do not independently
rewrite the same object definitions in OpenAPI YAML, TypeScript, MCP input, and
runtime validators.

## Explicit deferrals

Do not define speculative schemas for:

- accounts or browser sessions;
- OAuth clients, tokens, or scopes;
- Owner/Invite authorization;
- multi-Device routing;
- durable job delivery or reconciliation;
- Kubernetes resources; or
- likes, comments, follows, ranking, search, or other social features.

Add those contracts only after their domain lifecycles and authorization rules
are decided.
