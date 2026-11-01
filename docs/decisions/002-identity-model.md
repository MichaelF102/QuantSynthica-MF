# ADR 002 — Fund identity model

Status: Proposed

## Context
The CSV has one row per Yahoo/Morningstar symbol (`0P…BO`). Rows are share classes (Direct/Regular × Growth/IDCW variants): `base_fund` groups them and `n_share_classes` counts them. Net Assets repeat across classes. 975 rows have plan "Unspecified" and 415 have option "Unspecified". Insurer/ULIP funds (305) are not AMFI schemes.

## Decision
- **Internal surrogate IDs** for every table. Yahoo symbol, AMFI scheme code and ISIN are rows in `external_ids` (type, value, source, valid_from).
- Three levels: `fund_family` (= `base_fund`, derived and reviewed) → `scheme` (a specific share class: plan + option + IDCW mode/frequency) → external identifiers.
- `plan` and `option` keep an explicit `unspecified` value. Never infer Direct/Regular from the name unless the rule is recorded and versioned.
- Insurer and discontinued funds stay in the table with flags and are excluded from rankings by default.
- Aggregates over AUM operate at `fund_family` level.

## Consequences
Mapping to AMFI (Phase 3) is a scheme-level one-to-one assignment with explicit status (`confirmed`, `probable`, `ambiguous`, `unmapped`, `not_amfi_scheme`).
