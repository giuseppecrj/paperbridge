<!-- markdownlint-disable MD013 -->

# Code Review — Infrastructure / Engineering System

**Reviewed:** Integrated Wave 1 working tree (`cfeec74` plus uncommitted fixes)  
**Evidence:** lock check, Ruff, formatting, 103 tests, wheel build, and CLI smoke pass  
**Verdict:** **WAVE 1 INFRASTRUCTURE COMPLETE; opt-in HIL remains Wave 2**

## Execution status — 2026-08-01

Resolved and integrated, but not committed: enforced firmware digest, guarded erase, canonical port fallback, existing-path validation, repository-anchored deploy/provisioning paths, force-copy deployment, bounded application `system.ping` readiness, generated metadata cleanup, and removal of unenforced typechecker configuration.

No hardware operation was run during integration. CI, cloud infrastructure, and HIL recipes remain intentionally absent. The working tree still requires user-approved review/commit handling.

## 1. Current engineering system

| Area | Current state |
| --- | --- |
| Toolchain | mise pins Python 3.13.14, uv 0.11.8, just 1.56.0 |
| Dependencies | `uv.lock` resolves 35 packages |
| Host package | Hatchling builds `paperbridge-0.1.0-py3-none-any.whl` successfully |
| Tests | 103 host tests pass; firmware logic runs under CPython |
| Device tooling | esptool flash, mpremote deploy/verify, application CLI |
| Secrets | `.env`, device config, firmware downloads, captures, and secrets are ignored |
| CI | None; appropriate for the current single-machine hardware phase |
| Hardware testing | Real path verified manually; no reusable HIL command yet |

## 2. Facts changed since the previous review

- MicroPython was downloaded from the official URL, SHA-256 checked, flashed at `0x0`, and esptool verified written data.
- Deploy now checks for a MicroPython raw REPL before copying.
- Deploy force-copies individual `.py` files, preventing stale “up to date” code and future host `__pycache__` copies.
- CLI port output clearly distinguishes the device path from VID/PID.
- Hatchling packaging is proven by a successful wheel build.
- New regression tests cover deploy preflight/source selection, CLI mapping, and Ethernet static configuration.

## 3. Strengths

- Reproducible local toolchain with locked Python packages.
- One-command host gate: lint, format check, and tests.
- Flash, deployment, and application RPC are separate tools.
- Local config and firmware binary are not committed.
- Hardware dependencies are optional for ordinary tests.
- No premature GitHub Actions, cloud deployment, broker, or secret-manager infrastructure.
- Deployment now fails clearly if the device is blank or not running MicroPython.

## 4. Review findings and disposition

All flash/erase/path/port/readiness/tooling findings below were resolved in Wave 1. Operational documentation is synchronized; the HIL command remains Wave 2. The uncommitted-working-tree finding remains until the user explicitly approves commit handling.

### [High] Normal flash recipe does not enforce the known firmware digest

`flash_micropython.py` can verify `--sha256`, but `just flash-micropython` does not pass it. The operator can therefore flash the wrong/truncated variant through the documented path.

**Smallest fix:** Pass the verified digest from the recipe (and optionally enforce the known byte size). No new dependency or downloader abstraction.

### [High] Full flash erase lacks an explicit confirmation token

`erase-device` only checks that `PORT` is non-empty.

**Smallest fix:** Require `CONFIRM=erase`, mirroring the explicit cutter gate. Print the selected device path before erasing.

### [High] Tool paths depend on repository CWD

Deploy and provisioning use paths such as `Path("firmware/micropython")`. Commands fail or write in the wrong place when invoked outside the repository root.

**Smallest fix:** Derive repository root from `Path(__file__).resolve()` in each standalone tool.

### [High] No durable HIL/commissioning command exists

Manual live checks uncovered failures not represented by host tests. The project needs a reusable but opt-in hardware gate.

**Smallest fix after foundational streams:**

- `test-hardware-smoke`: ping/info, initialize, static config twice, link, probe; no print/cut.
- `test-hardware-acceptance`: one receipt/feed/cut with explicit operator confirmation and recorded device/firmware/test IDs.

Do not add these to ordinary `just test` or generic CI.

### [Medium] `PORT` and `PAPERBRIDGE_PORT` are competing names

Just recipes prefer `PORT`; the CLI prefers `PAPERBRIDGE_PORT`. Single-device fallback hides the inconsistency.

**Smallest fix:** Make just fall back to `PAPERBRIDGE_PORT` and document one canonical name. Keep explicit `--port` as the override.

### [Medium] Generated setuptools metadata remains tracked in HEAD

The working tree correctly ignores and deletes `paperbridge.egg-info`, but the initial commit still contains it.

**Smallest fix:** Land the ignore plus deletion with the packaging changes.

### [Medium] Pyright configuration is not an executable project check

`[tool.pyright]` exists, but no typechecker dependency or `just typecheck` exists. Current LSP auxiliary state has also produced stale findings.

**Recommendation:** Remove the dead config for now. Add typechecking later only with an installed tool and enforced command.

### [Medium] Port validation differs across tools

`verify_board.py` rejects numeric PID values and missing device paths. Flash and deploy do not share that guard.

**Smallest fix:** One tiny shared helper or duplicated three-line validation in flash/deploy; do not create a tooling framework.

### [Medium] Deploy returns before application readiness is proven

A command issued immediately after reset hit `SERIAL_READ_FAILED` during USB re-enumeration.

**Smallest fix:** After reset, perform a bounded readiness loop for the device path/application ping. Avoid an unconditional long sleep.

### [Medium] Working tree contains a large unlanded bring-up batch

Runtime, packaging, deploy, tests, docs status, and generated-file cleanup are all uncommitted. This makes later workstreams hard to isolate.

**Recommendation:** After review and user approval, integrate the current verified baseline as one focused bring-up fix before parallel feature work. Do not silently commit from the coordinator.

### [Low] No CI is acceptable now

The local gate is deterministic and fast. Add CI only when a second contributor/machine or PR workflow requires it.

### [Low] `clean` removes captures and the virtual environment

Captured printer bytes can be useful evidence. Consider splitting cache cleanup from destructive local artifact cleanup only if this causes real friction.

### [Low] Firmware status docs lag operations — resolved

Operational docs now record the verified MicroPython, RPC, Ethernet, endpoint, text, feed, and cut observations while preserving pending recovery and soak gates.

## 5. Resolved findings

- **Resolved:** Hatchling packaging uncertainty; wheel builds.
- **Resolved:** Deploy attempted file copies against vendor/blank firmware without a clear prerequisite message.
- **Resolved:** Recursive source deployment included host bytecode.
- **Resolved:** Changed firmware files could be skipped as “up to date”; source copies are forced.
- **Resolved:** Port output encouraged PID/path confusion.
- **Resolved:** Python floor mismatch with esptool; project requires Python ≥3.10 and mise pins 3.13.14.

## 6. Checks run for this refresh

| Check | Result |
| --- | --- |
| `mise exec -- uv lock --check` | Passed; 35 packages resolved |
| `mise exec -- just lint` | Passed |
| `mise exec -- just format-check` | Passed; 53 files formatted |
| `mise exec -- just test` | Passed; 103 tests |
| `mise exec -- uv build --wheel --out-dir /tmp/paperbridge-wave1-combined-dist` | Passed |
| `git diff --check` | Passed |
| Live USB RPC | Previously verified in this session |
| Live W5500 static config twice | Verified with MicroPython `ipconfig()` |
| Live link and printer probe | `link_up: True`, printer reachable |
| Physical text/feed/cut | User confirmed |

## 7. Coordination-ready infrastructure stream

Own only:

- `justfile`
- `tools/firmware/*`
- `tools/provisioning/*`
- `.gitignore`
- packaging/tooling sections of `pyproject.toml`
- corresponding host tests

Deliverables:

1. Enforced firmware checksum and guarded erase.
2. CWD-independent paths.
3. Canonical port environment behavior and shared validation.
4. Bounded post-deploy readiness.
5. Generated metadata cleanup and removal of dead typechecker config.

Do not add CI, cloud tooling, a general task framework, or HIL tests in this stream. HIL follows after runtime integration.

## 8. Top next actions

1. Preserve controlled HIL evidence IDs in `docs/hardware.md` — completed.
2. Run reconnect, fault-recovery, and soak gates before production claims.
3. Review and commit only when explicitly requested.
