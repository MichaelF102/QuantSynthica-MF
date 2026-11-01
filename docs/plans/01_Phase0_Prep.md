# Phase 0 — Prep (2–3 days)

## Goal
Remove ambiguity before writing app code.

## Tasks
- [ ] `git init`; add `.gitignore` (node_modules, .env, `data/bronze|silver|gold`, `__pycache__`, `.next`).
- [ ] Layout `data/raw/yahoo/` and move `yahoo_funds_clean.csv` there (keep the original untouched; record its SHA-256 in `data/raw/yahoo/MANIFEST.md`). Update prompts that reference the path.
- [ ] Review all 19 mockups in `ui/`; write `docs/architecture/screen_data_map.md`: one row per widget with columns: screen, widget, required fields, status (`available now` / `needs NAV history` / `needs new source`), notes.
- [ ] Reconcile navigation: mockup top bar (Market Overview, Fund Explorer, Screener, Analysis, Quant Models, Portfolios, Insights) vs. the 5-group, 22-page plan. Decide one and record it in `docs/decisions/001-navigation.md`.
- [ ] Extract design tokens from mockups into `docs/architecture/design_tokens.md` (navy/graphite backgrounds, blue/cyan accent, green/red, table density, type scale) and later as Tailwind theme.
- [ ] Note placeholder content in mockups (US funds, USD/₹ mix, 2025 dates) so it is never copied.
- [ ] Decision records: `002-identity-model` (scheme/plan/option), `003-direct-growth-primary-series`, `004-no-mock-data`.

## Deliverables
`docs/architecture/screen_data_map.md`, `design_tokens.md`, `docs/decisions/00{1..4}-*.md`, git repo, `MANIFEST.md`.

## Gate
Screen map reviewed and signed off; navigation fixed; repo initialised.
