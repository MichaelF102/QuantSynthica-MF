# ADR 004 — No mock data in product

Status: Proposed

## Decision
- Every figure displayed in the product comes from the API and, ultimately, from ingested data or from `quant_engine` calculations.
- Unavailable metrics show an explicit state: `—` plus tooltip ("Needs NAV history", "Source not connected"), never an invented number.
- Mockup values in `ui/` (names, returns, AUM, counts) are visual references only.
- Unit/integration test fixtures use clearly labelled synthetic data; synthetic data never enters seeded dev databases that a UI could display without a visible "DEMO DATA" banner.
- AI outputs may only restate numbers returned by tools (Phase 7).

## Enforcement
Lint rule/CI grep for hardcoded numeric arrays in `frontend/` view code; contract tests that every widget's data comes from a typed API call.
