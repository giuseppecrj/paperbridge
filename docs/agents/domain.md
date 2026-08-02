# Domain documentation

Paperbridge uses a single domain context.

Before exploring or changing behavior, read:

- `CONTEXT.md` at the repository root, when present.
- Relevant accepted decisions under `docs/adr/`.
- `AGENTS.md` for implementation, testing, and hardware-operation rules.

`CONTEXT.md` is a glossary of canonical domain language, not a specification or
implementation guide. Use its vocabulary in code, tests, issues, and reports.
Do not add general programming terms.

If a proposed change conflicts with an ADR, surface the conflict instead of
silently overriding the decision.

The `domain-modeling` skill creates and sharpens `CONTEXT.md` as terms are
resolved. ADRs should be added only for hard-to-reverse, surprising decisions
involving a real trade-off.
