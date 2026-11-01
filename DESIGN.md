# QuantSynthica Design System

The rules, tokens and component recipes behind the QuantSynthica UI (https://quant-synthica.vercel.app).
This file stands on its own, so it can be used to rebuild the same look in another project
(for example QuantSynthica Labs) without opening this repo. Every value below is copied from the
working code; the source file is named in each section.

---

## 1. Principles

1. **Institutional, data-first.** The UI looks like a professional research terminal, not a
   consumer app: dense but calm, dark navy, numbers aligned and in a monospace font.
2. **Real data only.** Never show made-up numbers, placeholder prices or demo series. A missing
   value renders as `—`. A missing section renders as an honest empty state ("Data not
   available"), never as fake content. A loading state uses skeletons, never zeros.
3. **One accent per meaning.**
   - Blue = navigation, selection, primary action.
   - Emerald = up/positive.
   - Rose = down/negative.
   - Amber = warning/neutral.
   - Purple = AI (SynthicaAI) and the Quantitative Lab only.
4. **No provider names in the UI.** Don't write data-vendor names (Yahoo, TradingView, Gemini…)
   in user-facing text. Use "QuantSynthica data" or "market data". News publisher credits are fine.
5. **Indian market conventions.**
   - Currency is `₹` with `en-IN` grouping (`1,23,45,678`).
   - Market cap is shown in `Cr`.
   - Percentages are signed (`+1.25%`).
   - Times are shown in IST.
6. **Dark first.** The product is designed in dark mode. Light mode exists, but all new screens
   are designed and checked in dark mode first.

---

## 2. Stack

| Concern | Choice |
|---|---|
| Framework | Next.js 14 App Router, React 18, TypeScript |
| Styling | Tailwind CSS 3 (utility classes inline, no CSS modules) |
| Icons | `lucide-react`, nothing else |
| Charts | Recharts (default); Plotly only for heavy scientific plots |
| Motion | `framer-motion`, used sparingly (landing page, reveals) |
| Class helper | `cn()` = `twMerge(clsx(...))` in `lib/utils.ts` |

Dark mode uses `darkMode: 'class'` (a `dark` class on `<html>`).

---

## 3. Fonts

```css
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap');
```

- **Inter** is the default for all UI text (`font-sans`).
- **IBM Plex Mono** (`font-mono`) is for every number, ticker, percentage, time range pill,
  badge score and small uppercase label. Numbers are *always* mono, so columns line up.

```js
// tailwind.config.js → theme.extend.fontFamily
sans: ['Inter', 'system-ui', 'sans-serif'],
mono: ['IBM Plex Mono', 'monospace'],
```

---

## 4. Colour

### 4.1 Theme tokens (CSS variables)

Components use the semantic Tailwind names (`bg-canvas`, `bg-surface`, `border-border`,
`text-primary`, `text-secondary`, `text-accent`, `text-positive`, `text-negative`,
`text-warning` and their `-subtle` variants), so they switch with the theme.

```css
:root {                       /* light */
  --bg-canvas: #FAFAF9;  --bg-surface: #FFFFFF;  --border-color: #E4E4E7;
  --text-primary: #18181B;  --text-secondary: #71717A;
  --accent-color: #2563EB;  --accent-subtle-color: #EFF6FF;
  --positive-color: #16803C;  --positive-subtle-color: #F0FDF4;
  --negative-color: #C62828;  --negative-subtle-color: #FEF2F2;
  --warning-color: #B45309;  --warning-subtle-color: #FFFBEB;
  --hover-bg: #F4F4F5;
}
.dark {                       /* dark (base) */
  --bg-canvas: #09090B;  --bg-surface: #18181B;  --border-color: #27272A;
  --text-primary: #F4F4F5;  --text-secondary: #A1A1AA;
  --accent-color: #3B82F6;  --accent-subtle-color: #1E293B;
  --positive-color: #22C55E;  --positive-subtle-color: #064E3B;
  --negative-color: #EF4444;  --negative-subtle-color: #451A1A;
  --warning-color: #F59E0B;  --warning-subtle-color: #2D1F06;
  --hover-bg: #27272A;
}
/* The signature navy palette. Wrap a page in .qs-market-theme to get it in dark mode. */
.dark .qs-market-theme {
  --bg-canvas: #080d1a;  --bg-surface: #0b1222;  --border-color: #1e293b;
  --text-primary: #f1f5f9;  --text-secondary: #94a3b8;
  --accent-color: #3b82f6;  --accent-subtle-color: #0e172e;  --hover-bg: #0e172e;
  --positive-subtle-color: #0b2a22;  --negative-subtle-color: #2c1219;  --warning-subtle-color: #2a1e08;
}
```

```js
// tailwind.config.js → theme.extend.colors
canvas: 'var(--bg-canvas)', surface: 'var(--bg-surface)', border: 'var(--border-color)',
primary: 'var(--text-primary)', secondary: 'var(--text-secondary)',
accent:   { DEFAULT: 'var(--accent-color)', hover: '#1D4ED8', subtle: 'var(--accent-subtle-color)' },
positive: { DEFAULT: 'var(--positive-color)', subtle: 'var(--positive-subtle-color)' },
negative: { DEFAULT: 'var(--negative-color)', subtle: 'var(--negative-subtle-color)' },
warning:  { DEFAULT: 'var(--warning-color)',  subtle: 'var(--warning-subtle-color)' },
```

### 4.2 The navy palette (dark mode)

These literal values appear throughout the market pages. Reuse them exactly.

| Role | Value |
|---|---|
| Navbar background | `bg-[#080C14]/95` + `backdrop-blur-md`, border `border-slate-800/80` |
| Page canvas | `#080d1a` |
| Card | `bg-[#0b1222]/95`, border `border-slate-800/90`, `shadow-lg shadow-black/20` |
| Raised card / regime card | `bg-[#0d1527]/90` |
| Tab bar / segmented control track | `bg-[#0b1120]/80` or `bg-[#0b1222]`, border `border-slate-800/80` |
| Dropdown menu | `bg-[#0B101C]`, border `border-slate-800`, `shadow-[0_18px_48px_-12px_rgba(0,0,0,0.65)]` |
| Mobile drawer | `bg-[#0C101A]` |
| Input background | `bg-[#0F172A]/70`, border `border-slate-700/50`, focus `border-blue-500` |
| Headings | `text-white` / `text-slate-100` |
| Body text | `text-slate-200` / `text-slate-300` |
| Muted text, labels | `text-slate-400`, faint: `text-slate-500` |
| Dividers | `border-slate-800`, row dividers `divide-slate-800/50` |
| Row hover | `hover:bg-slate-800/30` |
| Skeleton block | `bg-slate-800` (or `/50`) + parent `animate-pulse` |

### 4.3 Semantic colours (dark)

| Meaning | Text | Tinted chip / icon tile |
|---|---|---|
| Positive / up / bullish | `text-emerald-400` | `bg-emerald-500/10 border-emerald-500/20` (badges: `/15` and `/40`) |
| Negative / down / bearish | `text-rose-400` | `bg-rose-500/10 border-rose-500/20` |
| Warning / neutral | `text-amber-400` (alert text `text-amber-300`) | `bg-amber-500/10 border-amber-500/30` |
| Accent / info | `text-blue-400` | `bg-blue-500/10 border-blue-500/20` |
| AI / Lab | `text-purple-300` / `text-purple-400` | `bg-purple-500/15`, border `border-purple-500/40`, bg `#161028` |

Sparkline strokes: up `#10b981`, down `#f43f5e`.

### 4.4 Chart series palette

The order is fixed. Series *n* always gets colour *n*.

```ts
['#2563EB', '#16A34A', '#D97706', '#7C3AED', '#DC2626', '#0891B2', '#64748B', '#EA580C']
// blue, green, amber, purple, red, cyan, slate, orange
```

### 4.5 Gradients and glow

- **Title highlight word:** `bg-gradient-to-r from-blue-400 via-indigo-400 to-cyan-400 bg-clip-text text-transparent`.
- **Page header glow:** two blurred blobs behind the title:
  ```html
  <div class="absolute top-0 left-1/4 w-96 h-24 bg-blue-600/10 blur-3xl pointer-events-none rounded-full -z-10"></div>
  <div class="absolute top-0 right-1/4 w-96 h-24 bg-indigo-600/10 blur-3xl pointer-events-none rounded-full -z-10"></div>
  ```
- **Brand gradient** (logo swoosh): `#1D4ED8 → #38BDF8`.
- **Purple glow** (Lab button only): `shadow-[0_0_14px_rgba(168,85,247,0.15)]`.

---

## 5. Typography scale

The type is small and dense, deliberately. Data UIs use 10–14px.

| Use | Classes |
|---|---|
| Page title (H1) | `text-2xl sm:text-3xl font-extrabold tracking-tight text-primary`; the second word uses the gradient |
| Page subtitle | `text-xs sm:text-sm font-semibold tracking-wide` |
| Page description | `text-xs text-secondary leading-relaxed` |
| Card title (H2/H3) | `text-sm font-bold text-white tracking-wide` (`text-xs sm:text-sm` in tight cards) |
| Card subtitle | `text-[11px] text-slate-400` |
| Body / table cell | `text-xs` |
| Table header | `text-[10px] uppercase tracking-wider text-slate-400` |
| Micro label | `text-[10px] text-slate-400` (KPI captions) |
| Eyebrow / section kicker | `text-[10px] font-mono uppercase tracking-wider text-slate-400` |
| Brand subtitle | `text-[9px] uppercase tracking-[0.14em] font-semibold text-slate-400` |
| Big KPI number | `text-lg`–`text-2xl font-bold font-mono` |

---

## 6. Layout

### 6.1 Page container

Every page sits in `.app-container`:

```css
.app-container { width: 92%; max-width: 1700px; margin: 0 auto; padding: 0 1rem; }
@media (min-width: 640px)  { .app-container { padding: 0 1.5rem; } }
@media (min-width: 1024px) { .app-container { width: 94%; padding: 0 1.75rem; } }
@media (min-width: 1440px) { .app-container { width: 92%; padding: 0 2rem; } }
@media (max-width: 767px)  { .app-container { width: 100%; padding: 0 1rem; } }
```

A page is laid out as `<main className="app-container py-6 min-h-screen">`. Vertical rhythm
between page blocks is `space-y-6`.

### 6.2 Page anatomy (top to bottom)

1. **Sticky navbar**, 64px tall (`h-16`), full width, inner `w-[96%] max-w-[1720px]`.
2. **Page hero header**: title + gradient word, subtitle, description on the left; an optional
   summary card on the right (`lg:flex-row`). It ends with a bottom border (`border-b border-slate-800/60 pb-5`).
3. **Workspace tab bar**: a pill tab group (see 7.3). Tab state lives in the URL (`?tab=`).
4. **Content grid of cards.** Common grids:
   - KPI strip: `grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3`
   - Main + side: `grid grid-cols-1 lg:grid-cols-12 gap-4`, with `lg:col-span-8` / `lg:col-span-4`
   - Three-up: `grid grid-cols-1 md:grid-cols-3 gap-4`
5. **Site footer** (navy theme, `border-t`).

### 6.3 Spacing and radii

| Element | Value |
|---|---|
| Card padding | `p-4` (compact `p-3.5`) |
| Gap between cards | `gap-3` (KPIs) / `gap-4` (cards) |
| Card radius | `rounded-xl` |
| Button / input / tab radius | `rounded-lg` (small pills `rounded`, badges `rounded-full`) |
| Icon tile | `p-1.5 rounded-lg` holding a `w-4 h-4` icon |

### 6.4 Responsiveness

- Design for widths 1280, 1366, 1440, 1536 and 1920 and check each. Phones use a 16px gutter with
  no horizontal page scroll.
- The desktop nav shows from `xl` (1280px); below that a hamburger opens a drawer.
- Nav icons and the long Lab button label appear only from `min-[1760px]`, so the search box keeps
  its width on laptops.
- Wide tables and tab bars scroll inside their own container (`overflow-x-auto`), never the page.

---

## 7. Component recipes

Copy these class strings exactly.

### 7.1 Card

```tsx
<div className="rounded-xl border border-slate-800/90 bg-[#0b1222]/95 backdrop-blur-md p-4 h-full shadow-lg shadow-black/20">
  {/* header */}
  <div className="flex items-center justify-between gap-2 mb-3">
    <div className="flex items-center gap-2">
      <div className="p-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400">
        <Activity className="w-4 h-4" />
      </div>
      <div>
        <div className="flex items-center gap-1.5">
          <h3 className="text-sm font-bold text-white tracking-wide">Card title</h3>
          <button className="text-slate-500 hover:text-slate-300 transition-colors" title="What this shows">
            <Info className="w-3.5 h-3.5" />
          </button>
        </div>
        <p className="text-[11px] text-slate-400">One-line description</p>
      </div>
    </div>
    <button className="flex items-center gap-1 text-[11px] font-medium text-blue-400 hover:text-blue-300 transition-colors group">
      View All <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
    </button>
  </div>
  {/* body */}
</div>
```

- The icon-tile colour matches the card's meaning (emerald for "Top Performing", rose for "Worst Performing").
- Every card title has an `Info` tooltip that explains the metric.

### 7.2 Loading skeleton

A skeleton has the same outer shell as the card, plus `animate-pulse`, with grey bars where the
content will go. Never show `0`, `NaN` or an empty table while loading.

```tsx
<div className="rounded-xl border border-slate-800/90 bg-[#0b1222]/95 p-4 animate-pulse space-y-3 h-full">
  <div className="h-4 w-40 bg-slate-800 rounded" />
  <div className="space-y-2">{[...Array(5)].map((_, i) => <div key={i} className="h-9 bg-slate-800/50 rounded" />)}</div>
</div>
```

### 7.3 Workspace tab bar (pill tabs)

```tsx
<div className="w-full overflow-x-auto no-scrollbar py-2">
  <nav className="flex items-center gap-1.5 p-1 rounded-xl bg-[#0b1120]/80 border border-slate-800/80 backdrop-blur-md min-w-max">
    <button className={active
      ? 'flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs bg-blue-600 text-white shadow-lg shadow-blue-600/30 font-semibold'
      : 'flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}>
      <Icon className="w-3.5 h-3.5" /> Label
    </button>
  </nav>
</div>
```

### 7.4 Segmented control (time ranges)

Use this for 1D / 1W / 1M / 3M / 6M / 1Y and other short option sets.

```tsx
<div className="flex items-center p-0.5 rounded-lg bg-[#0b1222] border border-slate-800">
  <button className={sel
    ? 'px-2.5 py-1 rounded text-[11px] font-mono bg-blue-600 text-white shadow-sm font-semibold'
    : 'px-2.5 py-1 rounded text-[11px] font-mono font-medium text-slate-400 hover:text-white'}>1D</button>
</div>
```

### 7.5 Buttons

| Kind | Classes |
|---|---|
| Primary | `px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20 disabled:opacity-50 inline-flex items-center gap-1.5` |
| Secondary | `inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700/80 bg-slate-900/70 hover:bg-slate-800 hover:border-slate-600 text-slate-200 hover:text-white text-xs font-medium` |
| Text link | `text-[11px] font-medium text-blue-400 hover:text-blue-300` |
| Icon button | `p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60` |
| Lab / AI CTA | `rounded-lg border border-purple-500/40 hover:border-purple-400/70 bg-[#161028]/80 hover:bg-[#1E1538] text-white shadow-[0_0_14px_rgba(168,85,247,0.15)]` |

### 7.6 Badges

Status badges are rounded-full pills in mono caps:

```tsx
<div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-mono font-bold tracking-wider bg-emerald-500/15 border-emerald-500/40 text-emerald-400">
  <TrendingUp className="w-3.5 h-3.5" /> BULLISH (72/100)
</div>
```

Swap emerald for amber (NEUTRAL) or rose (BEARISH).

### 7.7 Data table

```tsx
<div className="w-full overflow-x-auto">
  <table className="w-full text-left border-collapse text-xs">
    <thead>
      <tr className="border-b border-slate-800 text-[10px] text-slate-400 uppercase tracking-wider">
        <th className="py-1.5 pr-2 w-6 text-center">#</th>
        <th className="py-1.5 px-2">Name</th>
        <th className="py-1.5 pl-2 text-right">1D Return</th>
      </tr>
    </thead>
    <tbody className="divide-y divide-slate-800/50">
      <tr className="hover:bg-slate-800/30 transition-colors">
        <td className="py-2 pr-2 text-center font-mono text-slate-400 text-[11px]">1</td>
        <td className="py-2 px-2 font-medium text-slate-200 truncate">Banks</td>
        <td className="py-2 pl-2 text-right font-mono font-bold text-emerald-400">+1.82%</td>
      </tr>
    </tbody>
  </table>
</div>
```

- Numbers are right-aligned and in mono.
- Text is left-aligned.
- Ranks are centred.
- A return is coloured by its sign; `—` stays `text-slate-500`.

### 7.8 KPI tile

```tsx
<div className="rounded-xl border border-slate-800/90 bg-[#0b1222]/95 p-3.5">
  <div className="flex items-center gap-1 text-[10px] text-slate-400 mb-0.5"><Icon className="w-3 h-3" /> Label</div>
  <div className="text-lg font-bold font-mono text-white">24,512.30</div>
  <div className="text-xs font-mono font-semibold text-emerald-400">+0.84%</div>
</div>
```

### 7.9 Inputs and search

```tsx
<div className="relative flex items-center bg-[#0F172A]/70 border border-slate-700/50 hover:border-slate-600 focus-within:border-blue-500 rounded-lg transition-colors">
  <Search className="ml-3 mr-2 h-3.5 w-3.5 text-slate-400" />
  <input className="w-full bg-transparent py-1.5 pr-3 text-xs text-slate-100 placeholder:text-slate-500 outline-none" />
</div>
```

The global search shows a `Ctrl K` keycap hint, in mono on a `border-slate-700` chip.

### 7.10 Dropdown menu (navbar)

- **Panel:** `absolute top-full mt-1 w-72 rounded-xl border border-slate-800 bg-[#0B101C] p-1.5 shadow-[0_18px_48px_-12px_rgba(0,0,0,0.65)] z-[60]`.
- **Item:** `flex items-start gap-3 rounded-lg px-2.5 py-2 hover:bg-slate-800/70 focus-visible:ring-1 focus-visible:ring-blue-500/70`.
- **Item content:** an icon `h-4 w-4 text-slate-400 group-hover:text-blue-400`, a title
  `text-[12.5px] font-medium text-slate-200`, and a description `text-[11px] text-slate-500`.
- **Behaviour:** opens on hover and on keyboard; Escape closes it.

### 7.11 Navbar

- **Bar:** `sticky top-0 z-50 bg-[#080C14]/95 backdrop-blur-md border-b border-slate-800/80`, `h-16`.
- **Left:** QS logo mark (`h-8 w-[51px] text-slate-200`), the "QuantSynthica" wordmark (`font-bold text-base text-white`)
  and the subtitle "FINANCIAL ANALYTICS PLATFORM".
- **Links:** `text-xs font-medium text-slate-300 hover:text-white px-2 py-4`.
  - Active: `text-blue-400 font-semibold` with a 2px underline `absolute bottom-0 left-2 right-2 h-0.5 bg-blue-500 rounded-full`.
  - The AI link uses purple instead of blue.
- **Right:** Lab CTA, search (it flexes and absorbs the squeeze), theme toggle, then avatar.

### 7.12 Alerts and banners

| Kind | Classes |
|---|---|
| Warning | `p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center justify-between` (with a `Retry` link on the right) |
| Error | same, with rose |
| Info | same, with blue |

Background-connection status is a single floating toast at the bottom centre
(`fixed bottom-5 left-1/2 -translate-x-1/2 rounded-xl border bg-[#0b1222]/95 backdrop-blur`), never a banner on each widget.

### 7.13 Empty state

Use a centred block inside the card: a muted icon (`h-8 w-8 text-slate-600`), one line
`text-sm text-slate-300`, and one helpful line `text-xs text-slate-500`. Say what is missing and
why; don't fill the space with sample data.

---

## 8. Charts (Recharts)

- **Grid:** `<CartesianGrid stroke="var(--border-color)" strokeDasharray="3 3" vertical={false} />`.
- **Axes:** tick `{{ fontSize: 10, fill: '#64748b' }}` (slate-500), `axisLine={false}`, `tickLine={false}`.
- **Tooltip:**
  ```ts
  contentStyle={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-color)', borderRadius: '6px', fontSize: '11px', color: 'var(--text-primary)' }}
  ```
- **Series:** take colours in order from the palette in 4.4. Lines are `strokeWidth={2}` with
  `dot={false}`. Area fills use a vertical `linearGradient` from `stopOpacity` 0.3 at the top to 0 at the bottom.
- **Up/down data:** emerald `#10b981` and rose `#f43f5e`. Candles are green up, red down.
- **Sizing:** charts sit in a fixed-height wrapper (`h-64` / `h-80`) with `ResponsiveContainer`.
- **Missing data:** gaps stay gaps. Don't interpolate or zero-fill.

---

## 9. Number formatting

All formatting goes through helpers. A non-numeric value becomes `—`.

```ts
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
export const fmtPrice = (v: unknown) =>
  isNum(v) ? `₹${v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—';
export const fmtPct = (v: unknown, digits = 2, signed = true) =>
  isNum(v) ? `${signed && v > 0 ? '+' : ''}${v.toFixed(digits)}%` : '—';
export const fmtX = (v: unknown) => (isNum(v) ? `${v.toFixed(1)}x` : '—');        // P/E, P/B
export const fmtInt = (v: unknown) => (isNum(v) ? v.toLocaleString('en-IN') : '—');
export const fmtCapCr = (v: unknown) =>                                             // market cap, input in ₹ Cr
  !isNum(v) || v <= 0 ? '—' : v >= 100000 ? `₹${(v / 100000).toFixed(2)}T` : `₹${Math.round(v).toLocaleString('en-IN')} Cr`;
```

- Index levels have 2 decimals and no `₹`.
- Ratios have 1 decimal plus `x`.
- Returns have 2 decimals, signed.
- Volatility and returns are annualised on 252 trading days.

---

## 10. Theming mechanics

- An inline script in `<head>` applies the saved theme (`localStorage.theme`, else the OS
  preference) before first paint, so pages never flash the wrong theme. Add
  `suppressHydrationWarning` to `<html>`.
- `<body className="bg-canvas text-primary font-sans min-h-screen flex flex-col antialiased">`.
- `.qs-light-surface` forces the light palette inside a section (landing sections on white).
- Print / "Save as PDF" switches to a white, high-contrast palette, hides the nav and footer
  (`print:hidden`), and adds `break-inside: avoid` on cards.
- Scrollbars are 6px wide: `var(--border-color)` thumb, `var(--bg-canvas)` track.

---

## 11. Brand

- **Logo:** the "QS" monogram, with bold stroked Q and S letters (stroke 13 in a 128×80 viewBox) cut
  by a rising swoosh.
  - Strokes above the swoosh use `currentColor`; strokes below it use the brand gradient
    `#1D4ED8 → #38BDF8`.
  - The favicon is the same drawing on a white rounded tile (`rx=26`).
  - Sources: `frontend/components/brand/QSLogoMark.tsx` and `frontend/app/icon.svg`. Copy both
    files when replicating.
- **Wordmark:** "QuantSynthica" in Inter bold, tight tracking. In the footer the word "Synthica" takes the accent colour.
- **Sister products:** in this app, the Quantitative Lab (`https://quantsynthicalab.vercel.app/`)
  is always shown in purple (see the Lab CTA in 7.5).
  - Option for QuantSynthica Labs: keep blue as the accent so the two apps look the same, or use
    purple (`bg-purple-600 hover:bg-purple-500`, `shadow-purple-600/30`) for active tabs and primary
    buttons to tie in with the Lab button.
  - Everything else stays identical: navy surfaces, emerald/rose for up/down, and typography.

---

## 12. Interaction and motion

- Transitions are `transition-colors` / `transition-all duration-150–200`. Nothing bounces.
- Hover affordances:
  - Arrow icons nudge `translate-x-0.5`.
  - The logo scales to `105%`.
  - Rows tint `bg-slate-800/30`.
- Keyboard:
  - Every interactive element is a real `<button>` or `<a>`, with `focus-visible:ring-1 ring-blue-500/70`.
  - Menus close on Escape.
  - Search opens with Ctrl/Cmd + K.
- Use `aria-current="page"` on the active nav item or tab, and `aria-live="polite"` on status toasts.
- Data reads retry on network errors and 502/503/504 (about 1 minute of back-off) before showing an
  error. Never fail a whole page because one widget failed; each card loads and errors on its own.

---

## 13. Replication checklist (for a new project)

1. Install `tailwindcss@3`, `lucide-react`, `recharts`, `clsx`, `tailwind-merge` (and `framer-motion` if needed).
2. Copy the tailwind `colors` and `fontFamily` extensions (section 4.1 and section 3).
3. Copy the `globals.css` tokens: `:root`, `.dark`, `.qs-market-theme`, `.app-container`, scrollbars,
   print block, and the Google Fonts import.
4. Add the theme-init script to the root layout and set the body classes (section 10).
5. Copy `QSLogoMark.tsx` and `icon.svg` (section 11).
6. Build the navbar (7.11), page hero header (4.5 + 5) and footer first, then use the card,
   tab, segmented control, table and KPI recipes for every screen.
7. Use the formatting helpers (section 9) for every number.
8. Check each screen at 1280 / 1440 / 1920 and on a phone, in dark mode, with loading, empty and
   error states, before calling it done.

---

## 14. In this repo (QuantSynthica Terminal: Next 16, Tailwind v4)

The Terminal follows this design system but is built on Next 16 and **Tailwind v4** (CSS-first, no `tailwind.config.js`). How the rules above map onto it:

| DESIGN.md | Terminal |
|---|---|
| Theme tokens (4.1) | `@theme inline` in `src/app/globals.css`: `--color-base` (canvas), `panel` (surface), `raised`, `hover`, `line` / `line-strong` (borders), `fg` / `strong` / `muted` / `faint` (text), `accent`, `up` / `down`, `warn`, `ai`. Each points at a `--qs-*` runtime variable. |
| Navy palette (4.2) | Applied to every page inside the app shell by `:root:has(#qs-app)`; the landing page keeps its own palette. `--qs-faint` is `#8090a6`, not slate-500: slate-500 is 3.9:1 on navy and fails WCAG AA for small text. |
| Fonts (3) | Inter and IBM Plex Mono through `next/font/google` (`--font-inter`, `--font-plex-mono`), self-hosted at build time. Canvas charts read the mono family from `--qs-font-mono` (`chartFontFamily`), since a canvas cannot resolve `var()`. |
| `cn()` = `twMerge(clsx())` (2) | `cn()` only joins class names. Components set their own classes, and callers pass layout classes, not conflicting colours. |
| Page container (6.1) | `@utility app-container`; `PageContainer` adds `py-6 space-y-6`. |
| Navbar (7.11) | `src/components/layout/top-nav.tsx`: Charts / Screener / Research menus, Watchlists link, purple SynthicaAI toggle; Settings is in the session menu. |
| Card (7.1) | `Panel` (`icon`, `tone`, `info`, `description`). |
| Pill tabs (7.3) | `<Tabs variant="pill">`; `underline` stays for sidebars and panels. |
| Segmented control (7.4) | `Segmented`; the Terminal's timeframe and range bars use the same look. |
| KPI tile (7.8), skeleton (7.2), banner (7.12) | `StatTile`, `Skeleton`, `Banner`. |
| Page header (4.5, 6.2) | `PageHeader` (`hero` for content pages, `bar` for full-height workstation pages). |
| Number formatting (9) | `src/lib/format.ts`: `formatMoney` and `formatCompactMoney` use en-IN and crore for INR, en-US otherwise. |
| No vendor names (1.4) | `displaySource()`: real data is "Market data"; generated test data keeps its TEST FIXTURE label. |
| Candles (8) | Default bullish `#10b981`, bearish `#f43f5e` (Settings can change them). |

`npm run test:e2e:design` checks every app page at 1280–1920 px and 375 px for horizontal scrolling and the design font, and runs axe-core (WCAG 2.0/2.1 A and AA, contrast included) at 1440 and 375 px and on each analysis-panel tab.

### Pitfall: `text-base` is a colour here
The theme defines a colour token named `base` (the page background), so Tailwind v4's `text-base` utility resolves to that colour, not to a 16px font size. Using it (or `sm:text-base`) makes text the same colour as the background. Use `text-[1rem]` for 16px.
