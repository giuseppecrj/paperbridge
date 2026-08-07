# Node vs Bun as production runtime for `apps/api`

Research performed 2026-08-07 against the current Paperbridge tree and
first-party Node, Bun, MCP, sharp, MQTT.js, and tsx documentation. These are
documentation and code facts, not a host or physical runtime proof under Bun.

## Workload under study

`apps/api` is a portable private REST / Streamable HTTP MCP / MQTT service:

| Concern | Current implementation |
| --- | --- |
| HTTP | Built-in `node:http` `createServer` (`apps/api/src/api-server.ts`) |
| MCP | `@modelcontextprotocol/server` + `@modelcontextprotocol/node` `toNodeHandler` / `hostHeaderValidation` (`apps/api/src/mcp-server.ts`) |
| MQTT | Long-lived `mqtt` client, publish + result subscription (`mqtt-job-client.ts`) |
| Images | `sharp` decode/resize to monochrome raster (`sharp-image-decoder.ts`) |
| Entry | `node --import tsx src/server.ts` |
| Tests | `node --import tsx --test tests/*.test.ts` (`node:test` + `node:assert`) |
| Shutdown | `process.once("SIGINT" \| "SIGTERM", …)` closes MCP, MQTT, HTTP |

Pinned workspace tools (`mise.toml`, root `package.json`): Node `26.3.0`, Bun
`1.3.14` as `packageManager`. API package engines implied by deps: MCP and
sharp require Node `>=20` / `>=20.9.0`.

## Existing product decision (repo)

Already decided and implemented:

- `apps/api/README.md`: portable **Node.js** TypeScript package; **Bun remains
  workspace tooling only**.
- ADR 0006 (superseded by 0007, still records the app boundary): one **Node.js**
  service; Bun manages workspaces/deps/scripts only; application code must not
  depend on Bun-specific runtime APIs.
- ADR 0007: run the **current Node entry point** under hardened systemd on
  exe.dev.
- Root scripts call `bun run --filter …`, which executes the **Node** scripts
  defined in `apps/api/package.json`.

This research re-checks whether that split should change for production.

## Comparison matrix (Paperbridge-relevant)

| Area | Node (current) | Bun as production runtime | Fit for `apps/api` |
| --- | --- | --- | --- |
| `node:http` server | Stable API; Stability 2 docs | Bun marks `node:http` fully implemented; **outgoing client request body buffered instead of streamed** | Server path likely OK on paper; still needs MCP mount proof under Bun |
| MCP SDK | `@modelcontextprotocol/node` is the **Node** adapter for `IncomingMessage` / `ServerResponse` | Official package README: for **Cloudflare Workers, Deno, Bun**, use web-standard transport from `@modelcontextprotocol/server` **directly**, not the Node adapter | Running the Node adapter on Bun is **off the documented path** |
| `mqtt` | First-class Node (and browser WS) client; engines `>=16` | No first-party Bun production claim; depends on Node net/tls/ws compatibility | Long-lived QoS 1 client is a hard dependency; must be proven, not assumed |
| `sharp` | Official prerequisite: Node-API v9, e.g. Node `>=20.9.0`; prebuilt binaries | Install docs list `bun add sharp`; Bun implements Node-API | Plausible; prove decode path on target OS/arch without bundling sharp |
| TypeScript execute | `tsx` is a **Node** TypeScript runner (`node --import tsx`) | Bun runs `.ts` natively; `tsx` is unnecessary and Node-oriented | Bun would drop `tsx`; Node keeps current scripts or a later compile step |
| Tests | Stable `node:test` via `node --test` | Bun: `node:test` **partial**; missing Node `--test` CLI mode; docs push `bun:test` | Current suite is Node-shaped; Bun production would force a test strategy decision |
| Signals / systemd | Node signal events document `SIGINT` / `SIGTERM`; ADR 0007 assumes Node under systemd | Bun documents `process.on("SIGINT")`; ctrl-c guide says call `process.exit()` explicitly to close | Shutdown must be proven with MQTT still open; do not assume Node semantics |
| Hosting docs | Cloud research + ADR 0007 assume Node process | Bun has Railway/Render/etc. guides | Both hostable; ops docs already Node |

## Dependency and API notes (cited)

### Node HTTP, process, tests

- `http.createServer`, `IncomingMessage`, `ServerResponse` are the Node HTTP
  surface Paperbridge mounts. Node documents the HTTP module as stable
  (Stability 2).
  Source: <https://nodejs.org/api/http.html>
- Signal events: listeners for `'SIGINT'` / `'SIGTERM'` receive the signal name;
  installing a listener changes default exit behavior.
  Source: <https://nodejs.org/api/process.html#signal-events>
- Test runner is stable; `import … from 'node:test'` and `node --test`.
  Source: <https://nodejs.org/api/test.html>

### Bun Node compatibility

- Bun states packages that work in Node but not Bun are Bun bugs; compatibility
  page is maintained against recent Node (doc claims Node v23 as reference).
  Source: <https://bun.com/docs/runtime/nodejs-compat>
  (MDX source: `oven-sh/bun` `docs/runtime/nodejs-compat.mdx`)
- `node:http`: fully implemented; **outgoing client request body is buffered
  instead of streamed**.
- `node:test`: **partial**; in-process API under `bun test` only; missing Node
  `--test` CLI runner mode and several features; docs recommend `bun:test`.
- `process`: mostly implemented; several APIs stubs/no-ops (not signal-specific
  in the matrix).
- Node-API: implemented so most native addons work.
  Source: <https://bun.com/docs/runtime/node-api>
- Signals: Bun supports `process.on` for OS signals; ctrl-c example requires
  explicit `process.exit()`.
  Sources: <https://bun.com/docs/guides/process/os-signals>,
  <https://bun.com/docs/guides/process/ctrl-c>
- Runtime runs TypeScript without a separate loader.
  Source: <https://bun.com/docs/runtime>

### `@modelcontextprotocol/*`

- `@modelcontextprotocol/node@2.0.0` engines: `node: >=20`. Description: Node.js
  middleware / adapters.
- Package README: Node adapters for Streamable HTTP with Node’s
  `IncomingMessage` / `ServerResponse`. **For web-standard runtimes (Cloudflare
  Workers, Deno, Bun, etc.), use `WebStandardStreamableHTTPServerTransport` from
  `@modelcontextprotocol/server` directly.**
- `toNodeHandler` uses `@hono/node-server` to bridge Node HTTP ↔ Web Fetch APIs
  (installed transitive dependency; visible in package dist).
- Serving docs: plain `node:http` mounts use `toNodeHandler` and Host/Origin
  validation.
  Source: <https://ts.sdk.modelcontextprotocol.io/v2/serving/http.html>
  and package README under `apps/api/node_modules/@modelcontextprotocol/node/`.

Implication: production Bun would either (a) run the Node adapter on Bun’s
Node-compat layer without official blessing, or (b) rewrite MCP mount to the
web-standard transport — a real code change, not a drop-in runtime swap.

### `mqtt`

- MQTT.js is “written in JavaScript for node.js and the browser”; v5 targets
  maintained Node (docs mention v18/v20 era; installed package engines
  `node: >=16.0.0`).
- Node path uses TCP/`tls.connect` (and `ws` for WebSockets); not a Bun-native
  client.
  Source: <https://github.com/mqttjs/MQTT.js/blob/main/README.md>

Implication: long-lived MQTT + TLS + QoS 1 correlation is the highest
operational risk if the runtime changes; compatibility is empirical.

### `sharp`

- Install lists `bun add sharp` alongside npm/pnpm/yarn.
- Prerequisites: **Node-API v9 compatible runtime**, e.g. **Node.js >= 20.9.0**.
- Prebuilt binaries for common macOS/Linux/Windows targets; exclude from
  bundlers.
  Source: <https://sharp.pixelplumbing.com/install>
- Installed `sharp@0.35.3` engines: `node: >=20.9.0`.

Implication: supported in principle on Bun via Node-API; still requires install
- decode proof on the production OS/arch (glibc vs musl matters for Linux
prebuilds).

### `tsx`

- “TypeScript Execute … easiest way to run TypeScript in **Node.js**”;
  prerequisites: Node.js installed.
  Source: <https://github.com/privatenumber/tsx> / tsx docs getting started
- Paperbridge production start is `node --import tsx …`, not `bun …`.

Implication: `tsx` is a Node production/dev runner choice. Bun production would
replace it with `bun src/server.ts` (or compile). It is not a Bun dependency.

## Recommendation

**Keep Node.js as the production runtime for `apps/api`. Keep Bun as workspace
package-manager / script orchestration only.**

Reasons (simplest well-supported path):

1. **Code and ADRs already assume Node** — HTTP server, MCP Node adapter, `tsx`,
   `node:test`, systemd entry, and README wording.
2. **MCP official guidance treats Bun as a web-standard runtime**, not as a host
   for `@modelcontextprotocol/node`. Drop-in Bun would fight that boundary or
   require a mount rewrite.
3. **No production win is required** — the process is a single always-on private
   API with MQTT; startup latency is irrelevant next to 15s job waits and broker
   RTT.
4. **Changing runtime adds proof surface** (MQTT, sharp, MCP stream, SIGTERM
   under systemd) without changing product behavior.

Do **not** select Bun for production unless a measured Node problem (memory,
deploy size, or a forced platform constraint) appears and the proof list below
is completed.

## If Bun is selected anyway — exact proof requirements

Do not claim Bun production readiness until **all** of the following pass on the
**same** Bun version that would ship (today’s pin: `1.3.14` or a deliberate
upgrade), on the **production OS/arch** (e.g. Linux glibc x64/arm64 for exe.dev):

1. **Install:** `bun install` yields a working `sharp` native binary (no
   rebuild failure); `sharp` remains unbundled.
2. **Unit/API tests:** either (a) full current suite under Node remains the
   merge gate and a **separate** Bun run of the same behavioral tests passes, or
   (b) suite is ported to a Bun-supported runner and passes with equal coverage
   (REST, MCP, image prepare, MQTT client fakes).
3. **HTTP + MCP:** live `POST /api/jobs`, `GET /health`, `GET /ready`, and
   Streamable HTTP MCP `paperbridge_print` against a Bun-started server;
   Host/Origin rejection still returns 403; tool cancellation via
   `context.mcpReq.signal` still aborts the waiter only.
4. **MQTT:** connect, subscribe to result topic, publish QoS 1 job, receive
   correlated result within timeout; reconnect after broker bounce; MQTT/TLS if
   production uses TLS; no silent half-open hang under idle.
5. **Images:** PNG and JPEG fixtures through `sharpImageDecoder` → prepared
   raster size limits identical to Node.
6. **Signals / supervision:** under systemd (or equivalent), `SIGTERM` runs
   shutdown (MCP `close`, MQTT `close`, HTTP `close`) and the process **exits**
   with a known code without requiring a kill -9; `SIGINT` same for interactive
   runs. Confirm whether explicit `process.exit` is required after cleanup.
7. **Entry scripts:** `start` / `mqtt:probe` do not use `tsx`; document Bun
   argv; no Bun-only APIs in application source (preserve ADR 0006 portability
   unless an ADR supersedes it).
8. **Regression policy:** any package that works on Node but fails on Bun is
   tracked as a Bun or adapter bug with a Node fallback still shippable.

Minimum evidence record: date, Bun version, OS/arch, commands, pass/fail for
each item above. Host-tested is not physically verified device delivery; keep
those claim classes separate per project rules.

## Non-goals

- Rewriting MCP to web-standard transport “for Bun readiness”
- Replacing MQTT.js
- Micro-benchmarking HTTP startup
- Changing package manager away from Bun for workspaces

## Primary sources

- Repo: `apps/api/package.json`, `apps/api/README.md`, `apps/api/src/server.ts`,
  `apps/api/src/api-server.ts`, `apps/api/src/mcp-server.ts`,
  `apps/api/src/sharp-image-decoder.ts`, `mise.toml`, root `package.json`,
  `docs/adr/0006-…`, `docs/adr/0007-…`
- Node HTTP: <https://nodejs.org/api/http.html>
- Node process signals: <https://nodejs.org/api/process.html#signal-events>
- Node test runner: <https://nodejs.org/api/test.html>
- Bun Node compatibility: <https://bun.com/docs/runtime/nodejs-compat>
- Bun Node-API: <https://bun.com/docs/runtime/node-api>
- Bun signals: <https://bun.com/docs/guides/process/os-signals>
- Bun ctrl-c / exit: <https://bun.com/docs/guides/process/ctrl-c>
- Bun runtime / TS: <https://bun.com/docs/runtime>
- MCP HTTP serving: <https://ts.sdk.modelcontextprotocol.io/v2/serving/http.html>
- `@modelcontextprotocol/node` README (installed 2.0.0): Node vs web-standard
  runtime split naming Bun explicitly
- sharp install: <https://sharp.pixelplumbing.com/install>
- MQTT.js README: <https://github.com/mqttjs/MQTT.js>
- tsx: Node-oriented TypeScript executor documentation / README

## Claim class

| Claim | Class |
| --- | --- |
| `apps/api` starts with Node + tsx and uses Node HTTP/MCP/mqtt/sharp | Implemented |
| ADR/README keep Bun as workspace tooling only | Documented (repo) |
| Bun Node-compat matrix and MCP Bun guidance above | Documented (upstream) |
| Bun can replace Node for this service without code changes | **Not proven** — would need the proof list |

No application or deployment code was changed by this research.
