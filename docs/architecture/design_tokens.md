# Design tokens (from `ui/` mockups)

Hex values below were **sampled from pixels** of `ui/01_Market_Overview1.png` (dark theme) and rounded. Anything marked *(est.)* was judged by eye. Treat as starting values; confirm in browser once the theme is built.

## Dark theme (default)
| Token | Value | Use |
|---|---|---|
| `--bg-page` | `#050E1A` | App background |
| `--bg-nav` | `#091524` | Top bar |
| `--bg-card` | `#0A1726` | Cards / panels |
| `--bg-input` | `#081229` | Search, selects |
| `--border` | `#0D192B` → use ~`#16263D` *(est.)* | Card borders (barely visible in mockup) |
| `--text-primary` | `#E8EEF7` *(est.)* | Headings, values |
| `--text-muted` | `#8FA0B8` *(est.)* | Labels, metadata |
| `--accent-blue` | `#2F7BFF` *(est.)* | Primary buttons, active tab, links |
| `--accent-cyan` | `#5CDDF9` | Logo, secondary accent |
| `--positive` | `#06B86C` | Gains, bars |
| `--negative` | `#F84B43` | Losses, bars |
| `--heat-pos` / `--heat-neg` | `#036340` / `#9A2930` | Heatmap extremes (interpolate) |
| `--warn` | `#F5B93A` *(est.)* | Amber series/status |
| `--purple` | `#8B5CF6` *(est.)* | Series colour |

Series palette order seen in charts: blue, green, amber, purple, red, cyan, grey. For categorical charts, validate colour-blind safety (add markers/patterns for >4 series) before shipping.

## Light theme
Not present in mockups. Required by the plan: derive from the same tokens (white/slate surfaces, same semantic hues darkened for contrast ≥ 4.5:1). Create in Phase 1 theme setup; design review before Phase 2 sign-off.

## Typography & density *(est.)*
- Sans-serif UI font (Inter or system); tabular numerals for all figures.
- Page title ~28–32px with accent-coloured keyword; card titles ~15px semibold; table text 12–13px; KPI values 26–32px.
- Row height ~28–32px in tables; card padding ~16px; grid gap ~12–16px. Desktop-first (mockups are 1536×1024).

## Components seen repeatedly
KPI tile with sparkline; period toggle (1M/3M/1Y/3Y/5Y/10Y); filter chip with ×; segmented tabs; heatmap table; score pill with green→red gradient; donut with centre total; horizontal bar list; top-bar nav with search (`/` shortcut), theme toggle, notifications, avatar.

## Conventions to enforce
Green = positive, red = negative, always with sign (`+`/`−`); Indian number formatting for money (₹ Cr, lakh/crore grouping); one date-range control pattern across charts; consistent axis units (%).
