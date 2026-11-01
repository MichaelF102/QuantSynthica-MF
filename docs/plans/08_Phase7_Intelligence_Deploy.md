# Phase 7 — Intelligence, AMC, Reports, Deployment (Weeks 12–14)

## AMC & manager intelligence
Rankings by category-adjusted results (median percentile across categories, minimum fund counts), AMC comparison, fund-family consistency, concentration. Not best-fund rankings. Manager pages only when manager history exists.

## AI Research Assistant
- Backend-only (Gemini or Claude). Tool-calling over the analytics engine: fund lookup, performance, risk, comparison, score explanation, portfolio analysis, report generation.
- Responses built from structured tool outputs; each figure carries calculation date and source; separate sections for facts, model interpretation, hypothetical projections.
- Guardrails: no invented numbers; refuse or state unavailability when data missing; no personalised investment advice; disclaimer text; prompt-injection hygiene on fund text fields.
- Logging of tool calls for audit; evaluation set of questions with expected tool usage.

## Reports
PDF and Excel: fund, comparison, risk, portfolio, quant research, backtest. Reports call the same service functions as dashboards; automated numbers-match test between report and API.

## Accounts & persistence
Auth (OAuth/email), per-user watchlists, alerts, saved screens, portfolios, research history, report storage; row-level ownership checks.

## Deployment
Vercel (frontend) + AWS (backend, worker, Postgres, Redis, object storage). Secrets in a manager, never in frontend. CI: backend tests, frontend build, migration check, API contract check, financial formula tests, data integrity checks. Health endpoints, logging, backups, scheduled NAV jobs with failure alerts.

## Readiness report
Completed modules, incomplete items, known limitations (survivor bias, mapping coverage, IDCW total return), deployment instructions.

## Gate
Test suite and production build green; numbers-match check passes; auth enforced on private endpoints; AI never outputs unsourced figures in evaluation.

---

## Status (2026-11-01): built locally, not deployed

See `phase7-progress.md` for the readiness report. Gate: test suites and production build are green; the report-vs-API numbers-match test passes; private endpoints (items, assistant) require a session; in evaluation the assistant emitted no unsourced figure. Not met: deployment to Vercel and Render (configuration written, not applied), live model validation (no API key), OAuth.
