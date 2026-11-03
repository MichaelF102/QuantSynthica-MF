import type { PlatformStats } from "@/lib/api";

/* Static markup of the landing page. Only the KPI list is generated, from the platform statistics (a figure that
   cannot be computed shows a dash). Links point at the real routes; the script (script.ts) turns same-site links into client navigations. */

const nIN = (v: number) => v.toLocaleString("en-IN");
const yr = (d: string | null | undefined) => (d ? d.slice(0, 4) : "");

function kpiRows(s: PlatformStats | null): string {
  const pct = (a: number | null | undefined, b: number | null | undefined) => (a != null && b ? (a / b) * 100 : null);
  const row = (o: { k: string; v: number | null | undefined; unit?: string; dec?: number; kind: "none" | "bar" | "dots"; note: string; src: string; x?: string; p?: number | null; text?: string }) => {
    const na = o.v == null;
    const asOf = s?.history_to ? ` · as of ${s.history_to}` : "";
    const extra = o.kind === "bar" ? `<span class="kli-bar"><i></i></span>` : o.kind === "dots" ? `<span class="kli-dots"></span>` : `<span class="kli-x">${o.x ?? ""}</span>`;
    return `<li class="kli" data-v="${na ? 0 : o.v}" data-dec="${o.dec ?? 0}" data-unit="${o.unit ?? ""}" data-kind="${o.kind}"${na ? ` data-na="1"` : ""}${o.kind === "bar" ? ` style="--p:${(o.p ?? 100).toFixed(1)}%"` : ""} data-note="${na ? "Not available right now" : o.note}" data-src="${o.src}${asOf}">
          <span class="kli-k">${o.k}</span><span class="kli-v">${na ? "—" : o.text}</span>${extra}
        </li>`;
  };
  const navM = s?.nav_observations != null ? s.nav_observations / 1e6 : null;
  const withNav = pct(s?.funds_with_nav_history, s?.funds);
  const scored = pct(s?.funds_scored, s?.funds);
  return [
    row({ k: "NAV observations", v: navM == null ? null : Math.round(navM * 10) / 10, unit: "M", dec: 1, kind: "none", note: `Daily NAVs, ${yr(s?.history_from)} to ${yr(s?.history_to)}`, src: "nav history", x: `${yr(s?.history_from)} to ${yr(s?.history_to)}`, text: navM == null ? "" : `${navM.toFixed(1)} M` }),
    row({ k: "Funds covered", v: s?.funds, kind: "bar", p: 100, note: `${s?.categories ?? "—"} categories`, src: "fund master", text: s?.funds == null ? "" : nIN(s.funds) }),
    row({ k: "Fund houses", v: s?.fund_houses == null ? null : Math.min(s.fund_houses, 200), kind: "dots", note: "One dot per fund house, excluding insurer-linked", src: "fund master", text: s?.fund_houses == null ? "" : nIN(s.fund_houses) }),
    row({ k: "Funds with NAV history", v: s?.funds_with_nav_history, kind: "bar", p: withNav, note: withNav == null ? "" : `${withNav.toFixed(1)}% of funds covered`, src: "nav history, linked to official records", text: s?.funds_with_nav_history == null ? "" : nIN(s.funds_with_nav_history) }),
    row({ k: "Funds scored", v: s?.funds_scored, kind: "bar", p: scored, note: scored == null ? "" : `${scored.toFixed(1)}% of funds covered`, src: `score ${s?.score_version ?? ""}`, text: s?.funds_scored == null ? "" : nIN(s.funds_scored) }),
    row({ k: "Strategies tested", v: s ? Math.min(s.strategies_tested, 200) : null, kind: "dots", note: "Point-in-time backtests", src: "backtest log", text: s ? nIN(s.strategies_tested) : "" }),
  ].join("\n");
}

const ARROW = `<svg class="icon arrow" viewBox="0 0 24 24"><path d="M7 17L17 7M9 7h8v8"/></svg>`;
const tile = (href: string, icon: string, title: string, text: string, d?: string) =>
  `<a class="tile rv" href="${href}"${d ? ` style="--d:${d}"` : ""}><span class="ic"><svg class="icon" viewBox="0 0 24 24">${icon}</svg></span>${ARROW}<h3>${title}</h3><p>${text}</p></a>`;

export function buildMarkup(s: PlatformStats | null): string {
  return `
<div class="progress" id="progress"></div>

<header class="nav" id="nav">
  <div class="wrap nav-inner">
    <a href="#top" class="brand" aria-label="QuantSynthica home">
      <span class="brand-logo"><img class="lg-dark" src="/brand/qs-logo-dark.png" alt="" /><img class="lg-light" src="/brand/qs-logo-light.png" alt="" /></span>
      <span><span class="brand-name">QuantSynthica</span><span class="brand-sub">MUTUAL FUNDS</span></span>
    </a>
    <nav class="links" aria-label="Primary">
      <a href="#explore" data-nav="explore">Platform</a>
      <a href="#engine" data-nav="engine">Quant engine</a>
      <a href="#risk" data-nav="risk">Risk</a>
      <a href="#portfolios" data-nav="portfolios">Portfolios</a>
      <a href="#regimes" data-nav="regimes">Regimes</a>
      <a href="#assistant" data-nav="assistant">AI assistant</a>
      <a href="#methodology" data-nav="methodology">Methodology</a>
    </nav>
    <div class="nav-right">
      <button type="button" class="theme-toggle" id="themeToggle" aria-label="Switch colour theme">Light</button>
      <a href="/overview" class="btn btn-primary btn-sm">Launch platform</a>
      <button class="burger" id="burger" aria-label="Open menu" aria-expanded="false">
        <svg class="icon" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
      </button>
    </div>
  </div>
</header>
<nav class="mobile-menu" id="mobileMenu" aria-label="Landing sections (mobile)">
  <a href="#explore">Platform</a>
  <a href="#engine">Quant engine</a>
  <a href="#risk">Risk</a>
  <a href="#portfolios">Portfolios</a>
  <a href="#regimes">Regimes</a>
  <a href="#assistant">AI assistant</a>
  <a href="#methodology">Methodology</a>
</nav>

<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <defs>
    <linearGradient id="ql-sg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#6aa8ff" stop-opacity=".35"/><stop offset="1" stop-color="#6aa8ff"/></linearGradient>
    <linearGradient id="ql-ag" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6aa8ff" stop-opacity=".18"/><stop offset="1" stop-color="#6aa8ff" stop-opacity="0"/></linearGradient>
  </defs>
</svg>

<main id="top">

<section class="hero" id="hero">
  <div class="hero-orb" aria-hidden="true"></div>
  <div class="hero-grid" aria-hidden="true"></div>
  <div class="hero-inner">
    <span class="hero-tag">Quantitative research for Indian mutual funds</span>
    <h1>Beyond Returns. <span class="l2">Into Intelligence.</span></h1>
    <p class="sub">Fund risk, drawdown behaviour and peer comparison, computed from official NAV records. Methodology is published with every result.</p>
    <div class="hero-cta">
      <a href="/overview" class="btn btn-primary">Launch the platform
        <svg class="icon" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>
      <a href="#methodology" class="btn btn-ghost">
        <svg class="icon" viewBox="0 0 24 24"><path d="M12 3l7 3v6c0 4.5-3 8-7 9-4-1-7-4.5-7-9V6z"/></svg>
        How it works</a>
    </div>
  </div>
</section>

<section class="kpi-scroll" id="kpiScroll" aria-label="Platform statistics">
  <div class="kpi-stick">
    <div class="wrap kpi-inner">
      <div class="kf">
        <span class="kf-k" id="kfK">NAV observations</span>
        <div class="kf-v"><span id="kfV">0</span><span class="kf-u" id="kfU">M</span></div>
        <div class="kf-n" id="kfN"></div>
        <div class="kf-src" id="kfSrc"></div>
      </div>
      <ol class="kl-list">
        ${kpiRows(s)}
      </ol>
    </div>
    <div class="kf-prog"><i id="kfProg"></i></div>
  </div>
</section>

<section id="ecosystem">
  <div class="wrap">
    <div class="section-head">
      <div class="rv"><span class="label">QuantSynthica ecosystem</span></div>
      <h2 class="rv" style="--d:.05s">One engine, <span class="soft">every view</span></h2>
      <p class="lead rv" style="--d:.1s">Each layer reads from the one below it, so a number on a fund page, in a report and in an assistant answer comes from the same calculation.</p>
    </div>
    <div class="pipe" id="pipe">
      <div class="pipe-track"></div>
      <div class="pipe-fill" id="pipeFill"></div>
      <div class="pipe-step" style="--c:var(--teal)"><span class="dot"></span><div class="n">01</div><div class="t">Data</div></div>
      <div class="pipe-step" style="--c:var(--blue)"><span class="dot"></span><div class="n">02</div><div class="t">Engine</div></div>
      <div class="pipe-step" style="--c:var(--amber)"><span class="dot"></span><div class="n">03</div><div class="t">Analytics</div></div>
      <div class="pipe-step" style="--c:var(--rose)"><span class="dot"></span><div class="n">04</div><div class="t">Lab</div></div>
      <div class="pipe-step" style="--c:var(--lime)"><span class="dot"></span><div class="n">05</div><div class="t">Assistant</div></div>
      <div class="pipe-step" style="--c:var(--sky)"><span class="dot"></span><div class="n">06</div><div class="t">Reports</div></div>
    </div>
    <div class="eco">
      <article class="cell span-4" style="--c:var(--teal)" data-spot>
        <span class="bar-top"></span>
        <div class="cell-visual">
          <div class="ledger">
            <div>Scheme register <em>official</em></div>
            <div>Daily NAV history <em>daily</em></div>
            <div>Fund profile mapping <em>mapped</em></div>
          </div>
        </div>
        <div class="cell-body"><div class="layer">Layer 01</div><h3>Data layer</h3>
          <p>Official scheme register and daily NAV history, mapped to fund profiles and checked before they are stored, with provenance kept on every record.</p></div>
      </article>
      <article class="cell span-2" style="--c:var(--blue)" data-spot>
        <span class="bar-top"></span>
        <div class="cell-visual">
          <svg class="spark" id="spark" viewBox="0 0 380 150" fill="none">
            <g><line class="gl" x1="0" y1="30" x2="380" y2="30"/><line class="gl" x1="0" y1="75" x2="380" y2="75"/><line class="gl" x1="0" y1="120" x2="380" y2="120"/></g>
            <path class="ar" fill="url(#ql-ag)" d="M0 120 C40 105 70 100 105 108 S170 90 200 96 S260 70 290 62 S340 28 380 22 L380 150 L0 150Z"/>
            <path class="ln" pathLength="100" d="M0 120 C40 105 70 100 105 108 S170 90 200 96 S260 70 290 62 S340 28 380 22"/>
            <circle class="end" cx="380" cy="22" r="4"/>
          </svg>
        </div>
        <div class="cell-body"><div class="layer">Layer 02</div><h3>Quant engine</h3>
          <p>One tested library computes returns, risk, scores, factor research, regimes and backtests.</p></div>
      </article>
      <article class="cell span-2" style="--c:var(--amber)" data-spot>
        <span class="bar-top"></span>
        <div class="cell-visual">
          <div class="bars">
            <i style="--h:38%;--i:0"></i><i style="--h:56%;--i:1"></i><i style="--h:44%;--i:2"></i><i style="--h:70%;--i:3"></i><i style="--h:50%;--i:4"></i><i class="hi" style="--h:92%;--i:5"></i><i style="--h:64%;--i:6"></i>
          </div>
        </div>
        <div class="cell-body"><div class="layer">Layer 03</div><h3>Analytics</h3>
          <p>Fund pages, comparison, screener and AMC views that read from the engine. Numbers are never re-derived.</p></div>
      </article>
      <article class="cell span-4" style="--c:var(--rose)" data-spot>
        <span class="bar-top"></span>
        <div class="cell-visual">
          <div class="lab">
            <div class="meter"><span><b></b></span><span><b></b></span><span><b></b></span><span><b></b></span></div>
            <div class="chips"><span class="chip">Builder</span><span class="chip">Optimiser</span><span class="chip">SIP / SWP</span><span class="chip">Stress test</span></div>
          </div>
        </div>
        <div class="cell-body"><div class="layer">Layer 04</div><h3>Portfolio lab</h3>
          <p>Builders, optimisers, SIP and SWP simulators, rebalancing and stress tests on your own mix.</p></div>
      </article>
      <article class="cell span-3" style="--c:var(--lime)" data-spot>
        <span class="bar-top"></span>
        <div class="cell-visual">
          <div class="answer">
            <div class="q">What did this fund return over 3 years?</div>
            <div class="txt caret" id="typed"></div>
            <span class="src">source and date shown</span>
          </div>
        </div>
        <div class="cell-body"><div class="layer">Layer 05</div><h3>AI assistant</h3>
          <p>Answers assembled from the same calculations, with the source and date of every figure.</p></div>
      </article>
      <article class="cell span-3" style="--c:var(--sky)" data-spot>
        <span class="bar-top"></span>
        <div class="cell-visual">
          <div class="docs">
            <div class="doc pdf"><b>PDF</b><i></i><i></i><i></i><i></i></div>
            <div class="doc xls"><b>XLSX</b><i></i><i></i><i></i><i></i></div>
          </div>
        </div>
        <div class="cell-body"><div class="layer">Layer 06</div><h3>Reports</h3>
          <p>PDF and Excel exports built from the same functions as the screens, tested to match.</p></div>
      </article>
    </div>
  </div>
</section>

<section id="explore">
  <div class="wrap">
    <div class="section-head">
      <div class="rv"><span class="label">Explore the platform</span></div>
      <h2 class="rv" style="--d:.05s">Everything is <span class="soft">one click away</span></h2>
      <p class="lead rv" style="--d:.1s">Every card opens a working page, not a mock-up.</p>
    </div>
    <div class="hive">
      ${tile("/overview", `<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>`, "Market overview", "Universe, categories and top performers at a glance.")}
      ${tile("/funds", `<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11"/>`, "Fund explorer", "Search and filter every fund, then open a full profile.", ".05s")}
      ${tile("/screener", `<path d="M4 6h16M7 12h10M10 18h4"/>`, "Screener", "Filter by category, risk and the QuantSynthica score.", ".1s")}
      ${tile("/comparison", `<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M6 8.5v3a3 3 0 003 3h6a3 3 0 013 3"/>`, "Comparison", "Up to five funds side by side, with correlation.", ".15s")}
      ${tile("/performance", `<path d="M3 17l5-5 4 4 8-8"/><path d="M15 8h6v6"/>`, "Performance analytics", "Trailing, rolling and calendar-year returns.", ".2s")}
      ${tile("/risk", `<path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z"/>`, "Risk analytics", "Volatility, drawdown, tail risk and downside measures.")}
      ${tile("/quant/scoring", `<path d="M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3"/>`, "Quant research lab", "Scoring, factor research, clustering, regimes, backtests.", ".05s")}
      ${tile("/portfolio/builder", `<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5h8v2M3 12h18"/>`, "Portfolios", "Build, optimise, simulate, rebalance and stress-test.", ".1s")}
      ${tile("/amc", `<path d="M4 20h16M6 20V9l6-5 6 5v11M10 20v-5h4v5"/>`, "AMC intelligence", "Fund houses compared by the median fund, not the best one.", ".15s")}
      ${tile("/assistant", `<path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>`, "AI research assistant", "Ask questions and get sourced answers.", ".2s")}
    </div>
  </div>
</section>

<section id="engine">
  <div class="wrap">
    <div class="section-head">
      <div class="rv"><span class="label">Quantitative intelligence engine</span></div>
      <h2 class="rv" style="--d:.05s">A score built from <span class="soft">five measurable factors</span></h2>
      <p class="lead rv" style="--d:.1s">Funds are ranked only against true peers (same category and plan). Each factor is a percentile within that peer group, and the weights are published.</p>
    </div>
    <div class="pie-layout rv" id="pie">
      <div class="pie-stage"><svg class="pie" viewBox="0 0 340 340" role="img" aria-label="The five parts of the score"></svg></div>
      <div class="pie-reveal">
        <article class="pie-card on" data-i="0">
          <span class="ic-box"><svg class="icon" viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg></span>
          <h4>QuantSynthica score weights</h4>
          <div class="sm">Methodology ${s?.score_version ? `score-${s.score_version.replace(/^score-/, "")}` : "score-1.0.0"}</div>
          <div class="pie-weights">
            <div class="w-row"><div class="top">Performance <b>25%</b></div><div class="trk"><i style="--w:25"></i></div></div>
            <div class="w-row"><div class="top">Risk-adjusted returns <b>25%</b></div><div class="trk"><i style="--w:25"></i></div></div>
            <div class="w-row"><div class="top">Consistency <b>20%</b></div><div class="trk"><i style="--w:20"></i></div></div>
            <div class="w-row"><div class="top">Downside protection <b>15%</b></div><div class="trk"><i style="--w:15"></i></div></div>
            <div class="w-row"><div class="top">Momentum <b>10%</b></div><div class="trk"><i style="--w:10"></i></div></div>
            <div class="w-row thin"><div class="top">Fund stability <b>5%</b></div><div class="trk"><i style="--w:5"></i></div></div>
          </div>
          <p class="pie-foot">Fund stability needs data not yet connected; the other weights are renormalised.</p>
          <ul class="pie-points">
            <li>Each factor is a percentile within its own peer group.</li>
            <li>Weights are published with every score version.</li>
            <li>When a factor has no data, the remaining weights are rescaled, never zero-filled.</li>
          </ul>
        </article>
        <article class="pie-card" data-i="1">
          <span class="ic-box"><svg class="icon" viewBox="0 0 24 24"><path d="M12 3v18M5 7h14M7 7l-3 6h6zM17 7l-3 6h6z"/></svg></span>
          <h4>Peer-relative, not absolute</h4>
          <p>A debt fund is never ranked against an equity fund. Missing metrics are never filled with zero.</p>
          <ul class="pie-points">
            <li>Ranking uses the same category and plan only.</li>
            <li>A missing metric stays missing, shown as a dash with its reason.</li>
            <li>Peer averages exclude the fund being scored.</li>
          </ul>
        </article>
        <article class="pie-card" data-i="2">
          <span class="ic-box"><svg class="icon" viewBox="0 0 24 24"><path d="M4 20l4-4 3 3 9-9"/><path d="M14 10h6v6"/></svg></span>
          <h4>Tested before it is trusted</h4>
          <p>Factors are checked for rank correlation with later peer-relative returns, using only information available at each date.</p>
          <ul class="pie-points">
            <li>Each factor is tested against what happened after the scoring date.</li>
            <li>Only data available on that date is used, so there is no look-ahead.</li>
            <li>A factor is judged on its record, not on how plausible it sounds.</li>
          </ul>
        </article>
        <article class="pie-card" data-i="3">
          <span class="ic-box"><svg class="icon" viewBox="0 0 24 24"><circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M8 7.5l3 8M16 7.5l-3 8"/></svg></span>
          <h4>Clustering and statistics</h4>
          <p>K-Means, hierarchical, mixture and density clustering inside each asset tier, plus correlation and distribution views.</p>
          <ul class="pie-points">
            <li>Four clustering methods, run inside each asset tier.</li>
            <li>Correlation views show how funds move together.</li>
            <li>Distribution views show how returns are spread within each group.</li>
          </ul>
        </article>
        <article class="pie-card" data-i="4">
          <span class="ic-box"><svg class="icon" viewBox="0 0 24 24"><path d="M4 5h16l-6 8v5l-4 2v-7z"/></svg></span>
          <h4>Backtested honestly</h4>
          <p>Nine selection strategies tested with delay, trading costs and exit loads, against an equal-weighted benchmark of the same funds.</p>
          <ul class="pie-points">
            <li>Nine selection strategies, each tested with a realistic delay.</li>
            <li>Trading costs and exit loads are deducted before results are shown.</li>
            <li>The benchmark is an equal-weighted average of the same funds.</li>
          </ul>
        </article>
      </div>
    </div>
    <p class="evidence rv">What the evidence says: momentum showed a positive link to later peer-relative returns, but no strategy, including the composite score, beat the benchmark after costs. The score is a research indicator, not a prediction. <a class="textlink" href="/quant/factors">See the factor research</a>.</p>
  </div>
</section>

<section id="risk">
  <div class="wrap">
    <div class="section-head">
      <div class="rv"><span class="label">Risk and performance analytics</span></div>
      <h2 class="rv" style="--d:.05s">See the risk <span class="soft">behind the return</span></h2>
      <p class="lead rv" style="--d:.1s">Two funds with the same return can have very different drawdowns. Every window shows both, side by side.</p>
    </div>
    <div class="compass-layout rv" id="compassWrap">
      <div class="compass"><svg class="compass-svg" viewBox="0 0 400 400" role="group" aria-label="Risk categories. Hover a quadrant to see its metrics."></svg></div>
      <div class="cp" id="cp">
        <div class="cp-idx" id="cpIdx">Category 01 of 4</div>
        <h3 id="cpTitle">Returns</h3>
        <p id="cpDesc"></p>
        <ul class="cp-list" id="cpList"></ul>
      </div>
    </div>
    <p class="compass-hint">Hover or tab through a quadrant to see its metrics.</p>
    <div class="spec-grid">
      <article class="spec rv">
        <div class="spec-top"><span>A</span><span>Conventions</span></div>
        <h4>Stated conventions</h4>
        <dl class="spec-rows"><div><dt>Annualisation</dt><dd>252 days</dd></div><div><dt>CAGR basis</dt><dd>365.25 days</dd></div><div><dt>Risk-free rate</dt><dd>Proxy, labelled</dd></div></dl>
        <p>252-day annualisation and a 365.25-day CAGR. The risk-free rate is a proxy built from overnight and liquid funds, labelled as such.</p>
      </article>
      <article class="spec rv" style="--d:.08s">
        <div class="spec-top"><span>B</span><span>Benchmark</span></div>
        <h4>Peer benchmark, not an index</h4>
        <dl class="spec-rows"><div><dt>Method</dt><dd>Equal-weighted</dd></div><div><dt>Universe</dt><dd>Surviving funds</dd></div><div><dt>Peer set</dt><dd>Same category and plan</dd></div><div><dt>Fund itself</dt><dd>Excluded</dd></div></dl>
        <p>The benchmark is the equal-weighted average of surviving funds in the same category and plan, excluding the fund itself.</p>
      </article>
      <article class="spec rv" style="--d:.16s">
        <div class="spec-top"><span>C</span><span>Data quality</span></div>
        <h4>Guards against bad data</h4>
        <dl class="spec-rows"><div><dt>NAV jumps</dt><dd>Flagged</dd></div><div><dt>Low volatility</dt><dd>Ratios withheld</dd></div></dl>
        <p>Implausible NAV jumps are flagged, and ratios are withheld when volatility is too low to mean anything.</p>
      </article>
    </div>
    <p class="open-links rv">Open <a class="textlink" href="/performance">performance analytics</a> or <a class="textlink" href="/risk">risk analytics</a>.</p>
  </div>
</section>

<section id="portfolios">
  <div class="wrap">
    <div class="section-head">
      <div class="rv"><span class="label">Portfolio engineering</span></div>
      <h2 class="rv" style="--d:.05s">From a list of funds to <span class="soft">a portfolio you understand</span></h2>
      <p class="lead rv" style="--d:.1s">Pick up to 40 Growth funds and see how the mix behaves, where its risk really comes from, and how different weighting rules change it.</p>
    </div>
    <div class="desk rv" id="desk">
      <div class="desk-head">
        <span class="desk-tag">Portfolio desk, illustrative mix</span>
        <div class="presets"><button type="button" data-p="equal" class="on">Equal weight</button><button type="button" data-p="defensive">Defensive</button></div>
      </div>
      <div class="desk-body">
        <div class="channels" id="channels"></div>
        <aside class="desk-side">
          <div class="column" id="column"></div>
          <div class="ro"><span>Total</span><b id="total">100%</b></div>
          <div class="ro"><span>Effective number of funds</span><b id="effN">5.0</b></div>
          <p class="desk-note">Risk share is weight multiplied by an illustrative volatility. The weights and volatilities here are an example, not engine data.</p>
        </aside>
      </div>
    </div>
    <div class="loop-layout rv" id="loopWrap">
      <div class="loop"><svg class="loop-svg" viewBox="0 0 460 460" role="group" aria-label="Portfolio lifecycle, six steps"></svg></div>
      <div class="lp" id="lp"><div class="lp-k" id="lpK"></div><h3 id="lpT"></h3><p id="lpD"></p><div class="lp-chips" id="lpC"></div><div class="lp-steps" id="lpS"></div></div>
    </div>
    <p class="loop-hint">Hover a step to preview it. Click one to stop the cycle.</p>
    <p class="pf-foot rv">Expected returns are shrunk historical averages, not forecasts. Historical results and hypothetical projections are always labelled apart, and taxes are not modelled. <a class="textlink" href="/portfolio/builder">Open the portfolio builder</a>.</p>
  </div>
</section>

<section id="regimes">
  <div class="wrap">
    <div class="section-head">
      <div class="rv"><span class="label">Market regime intelligence</span></div>
      <h2 class="rv" style="--d:.05s">Know the market's <span class="soft">current mood</span></h2>
      <p class="lead rv" style="--d:.1s">Regimes are measured on the equal-weighted average of Direct-plan equity Growth funds that exist today (survivors only). The timeline below is an illustrative sketch of the three labels, not stored history; the live reading is on the <a class="textlink" href="/quant/regimes">regimes page</a>.</p>
    </div>
    <div class="tl rv" id="tl">
      <div class="tl-read">
        <div class="tl-date"><span class="tl-k">Illustrative reading as of</span><b id="tlDate">2026-10</b></div>
        <div class="tl-vals">
          <div><span>Trend</span><b data-val="trend">Bear</b></div>
          <div><span>Volatility</span><b data-val="vol">Low</b></div>
          <div><span>Hidden state</span><b data-val="state">Calm</b></div>
        </div>
        <button type="button" class="tl-btn" id="tlReplay">Replay 2006 to 2026</button>
      </div>
      <div class="tl-stack" id="tlStack" tabindex="0" role="slider" aria-label="Choose a month" aria-valuemin="0" aria-valuemax="249">
        <div class="tl-cursor" id="tlCursor"></div>
        <div class="tl-lane"><div class="tl-lane-n"><span>Trend</span></div><div class="tl-track" data-track="trend"></div></div>
        <div class="tl-lane"><div class="tl-lane-n"><span>Volatility</span></div><div class="tl-track" data-track="vol"></div></div>
        <div class="tl-lane"><div class="tl-lane-n"><span>Hidden state</span></div><div class="tl-track" data-track="state"></div></div>
      </div>
      <div class="tl-axis" id="tlAxis"></div>
      <div class="tl-legend">
        <div class="rc" style="--c:var(--teal)">
          <div class="rc-top"><span class="rc-n">01</span><span class="rc-cap">Share of months</span></div>
          <h4>Trend</h4>
          <div class="rc-glyph">
            <svg viewBox="0 0 240 56" aria-hidden="true">
              <rect x="0" y="50" width="80" height="4" rx="2" fill="#2dd4bf" opacity=".85"/><rect x="82" y="50" width="68" height="4" rx="2" fill="#3b4a63"/><rect x="152" y="50" width="88" height="4" rx="2" fill="#f07a8f" opacity=".85"/>
              <path class="draw" pathLength="1" d="M0 38 C20 28 34 44 55 30 S90 12 110 25 S150 46 170 21 S210 10 240 17" fill="none" stroke="#e6ebf3" stroke-width="1.6" stroke-linecap="round"/>
              <path class="draw" pathLength="1" d="M0 33 C40 29 80 32 120 27 S200 18 240 22" fill="none" stroke="#6aa8ff" stroke-width="1.2" stroke-dasharray="3 3"/>
            </svg>
          </div>
          <div class="rc-share" data-share="trend"></div>
          <p>Bull, bear or sideways from price versus its moving average, using only past data.</p>
        </div>
        <div class="rc" style="--c:var(--blue)">
          <div class="rc-top"><span class="rc-n">02</span><span class="rc-cap">Share of months</span></div>
          <h4>Volatility</h4>
          <div class="rc-glyph">
            <svg viewBox="0 0 240 56" aria-hidden="true">
              <rect x="0" y="16" width="78" height="8" rx="4" fill="#6aa8ff" opacity=".85"/><rect x="81" y="16" width="78" height="8" rx="4" fill="#3b4a63"/><rect x="162" y="16" width="78" height="8" rx="4" fill="#e5b35c" opacity=".85"/>
              <path d="M146 4 L152 12 L140 12 Z" fill="#e6ebf3"/>
              <text x="0" y="44" font-size="9" fill="#7d8798" font-family="monospace">LOW</text><text x="120" y="44" font-size="9" fill="#7d8798" font-family="monospace" text-anchor="middle">NORMAL</text><text x="240" y="44" font-size="9" fill="#7d8798" font-family="monospace" text-anchor="end">HIGH</text>
            </svg>
          </div>
          <div class="rc-share" data-share="vol"></div>
          <p>Low, normal or high from the realised volatility percentile at each date.</p>
        </div>
        <div class="rc" style="--c:var(--violet)">
          <div class="rc-top"><span class="rc-n">03</span><span class="rc-cap">Share of months</span></div>
          <h4>Hidden state</h4>
          <div class="rc-glyph">
            <svg viewBox="0 0 240 56" aria-hidden="true">
              <line class="draw" pathLength="1" x1="42" y1="22" x2="110" y2="22" stroke="#3b4a63" stroke-width="1.5"/><line class="draw" pathLength="1" x1="130" y1="22" x2="198" y2="22" stroke="#3b4a63" stroke-width="1.5"/>
              <circle cx="30" cy="22" r="9" fill="#a78bfa"/><circle cx="120" cy="22" r="9" fill="#3b4a63"/><circle cx="210" cy="22" r="9" fill="#f07a8f"/>
              <text x="30" y="46" font-size="9" fill="#7d8798" font-family="monospace" text-anchor="middle">CALM</text><text x="120" y="46" font-size="9" fill="#7d8798" font-family="monospace" text-anchor="middle">MIXED</text><text x="210" y="46" font-size="9" fill="#7d8798" font-family="monospace" text-anchor="middle">STRESSED</text>
            </svg>
          </div>
          <div class="rc-share" data-share="state"></div>
          <p>A statistical model fitted only on earlier data; states are named by how volatile they are.</p>
        </div>
      </div>
    </div>
  </div>
</section>

<section id="assistant">
  <div class="wrap">
    <div class="section-head">
      <div class="rv"><span class="label">AI research assistant</span></div>
      <h2 class="rv" style="--d:.05s">Ask in plain English. <span class="soft">Get sourced answers.</span></h2>
      <p class="lead rv" style="--d:.1s">The assistant looks things up in the platform's own calculations. It never writes a figure that is not in a tool result.</p>
    </div>
    <div class="ai-widget rv" id="ai">
      <div class="aw-bar">
        <div class="aw-title"><span class="aw-dot"></span>Research assistant<span class="aw-meta">sample session</span></div>
        <div class="aw-tools"><span class="aw-check" id="aiVerify">3 of 3 figures match the log</span><button type="button" class="textlink aw-replay" id="aiReplay">Replay</button></div>
      </div>
      <div class="aw-body">
        <div class="aw-main">
          <div class="aw-q"><span class="aw-lbl">Question</span><p><span id="aiQ"></span><i class="aw-caret"></i></p></div>
          <div class="aw-ans"><span class="aw-lbl">Answer</span><div class="ans" id="aiAns"></div></div>
          <ol class="notes">
            <li class="fn tk" data-n="1"><span class="fn-n">1</span>Volatility over 3 years, annualised. Source: nav history, as of 2026-10-31.</li>
            <li class="fn tk" data-n="2"><span class="fn-n">2</span>Largest peak-to-trough fall in the same window. Source: nav history, as of 2026-10-31.</li>
            <li class="fn tk" data-n="3"><span class="fn-n">3</span>Excess return per unit of volatility, using the proxy risk-free rate. Source: nav history and proxy, as of 2026-10-31.</li>
          </ol>
        </div>
        <aside class="aw-side">
          <span class="aw-lbl">Tool calls</span>
          <div class="trace" id="aiTrace">
            <div class="trow" data-n="1"><button type="button" class="tcall" aria-expanded="false"><span class="ts">22:46:03</span><code>volatility(fund, window=3Y)</code><span class="res">14.2%</span><span class="chev" aria-hidden="true"></span></button>
              <div class="tdet"><dl><div><dt>Method</dt><dd>v1.0</dd></div><div><dt>Source</dt><dd>nav history</dd></div><div><dt>As of</dt><dd>2026-10-31</dd></div><div><dt>Unit</dt><dd>annualised %</dd></div></dl></div></div>
            <div class="trow" data-n="2"><button type="button" class="tcall" aria-expanded="false"><span class="ts">22:46:03</span><code>max_drawdown(fund, window=3Y)</code><span class="res">-18.6%</span><span class="chev" aria-hidden="true"></span></button>
              <div class="tdet"><dl><div><dt>Method</dt><dd>v1.0</dd></div><div><dt>Source</dt><dd>nav history</dd></div><div><dt>As of</dt><dd>2026-10-31</dd></div><div><dt>Unit</dt><dd>% from peak</dd></div></dl></div></div>
            <div class="trow" data-n="3"><button type="button" class="tcall" aria-expanded="false"><span class="ts">22:46:04</span><code>sharpe(fund, window=3Y, rf=proxy)</code><span class="res">0.84</span><span class="chev" aria-hidden="true"></span></button>
              <div class="tdet"><dl><div><dt>Method</dt><dd>v1.0</dd></div><div><dt>Source</dt><dd>nav history, proxy rate</dd></div><div><dt>As of</dt><dd>2026-10-31</dd></div><div><dt>Unit</dt><dd>ratio</dd></div></dl></div></div>
          </div>
        </aside>
      </div>
      <div class="aw-input"><span class="aw-prompt">query&gt;</span><span class="aw-ph">Ask about any fund, category or metric</span></div>
    </div>
    <p class="aw-fine">The figures in this sample session are an example, not live results. Available to signed-in users. <a class="textlink" href="/assistant">Open the assistant</a>.</p>
  </div>
</section>

<section id="methodology">
  <div class="wrap">
    <div class="section-head">
      <div class="rv"><span class="label">Research methodology and transparency</span></div>
      <h2 class="rv" style="--d:.05s">We show our work, <span class="soft">including the limits</span></h2>
      <p class="lead rv" style="--d:.1s">Trust comes from being able to check. Here is what is versioned, what is tested, and where the method is weak.</p>
    </div>
    <div class="fn-wrap">
      <div class="fn-left rv">
        <div class="fn-tools"><span>Live run</span><button type="button" class="textlink fn-replay" id="fnReplay">Replay</button></div>
        <div class="fn-stage" id="fnStage">
          <span class="fn-in">data in</span>
          <svg id="fnSvg" viewBox="0 0 600 640" aria-hidden="true"></svg>
          <span class="fn-out" id="fnOut">published number</span>
        </div>
        <ol class="fn-leaks" id="fnLeaks">
          <li><span class="lid">L-01</span><span>Survivorship bias: only funds that exist today are included, which flatters category averages and rankings.</span></li>
          <li><span class="lid">L-02</span><span>No licensed index: benchmarks are category averages and the risk-free rate is a proxy from overnight and liquid funds.</span></li>
          <li><span class="lid">L-03</span><span>Only Growth options with a confirmed link to official records are analysed, because IDCW NAVs leave out payouts.</span></li>
          <li><span class="lid">L-04</span><span>In backtests no selection rule, including the composite score, beat the benchmark after costs. The score is not a prediction.</span></li>
          <li><span class="lid">L-05</span><span>Category labels are today's labels, not point-in-time; taxes are not modelled.</span></li>
        </ol>
      </div>
      <ol class="fn-rules" id="fnRules">
        <li class="rv" style="--c:var(--blue)"><span class="fn-bar"></span><div><span class="rid">M-01</span><h4>Versioned methods</h4><p>Every metric, score, optimiser and simulator carries a methodology version, shown with the result.</p><code>method v1.0 · printed beside every figure</code></div><span class="fn-stamp">Enforced</span></li>
        <li class="rv" style="--c:var(--teal);--d:.06s"><span class="fn-bar"></span><div><span class="rid">M-02</span><h4>Point-in-time research</h4><p>Past scores, regime labels and trades are tested to be unchanged when future data is altered.</p><code>future altered &rarr; past unchanged</code></div><span class="fn-stamp">Tested</span></li>
        <li class="rv" style="--c:var(--violet);--d:.12s"><span class="fn-bar"></span><div><span class="rid">M-03</span><h4>Reports match screens</h4><p>Excel and PDF reports come from the same functions as the dashboards, and a test compares each number one by one.</p><code>excel = pdf = dashboard</code></div><span class="fn-stamp">Tested</span></li>
        <li class="rv" style="--c:#9aa6b8;--d:.18s"><span class="fn-bar"></span><div><span class="rid">M-04</span><h4>Missing means missing</h4><p>A dash and a reason, never a placeholder, a zero or an invented value.</p><code>- &nbsp;reason</code></div><span class="fn-stamp">Enforced</span></li>
      </ol>
    </div>
    <a class="textlink rd-link rv" href="/coverage">See data coverage</a>
  </div>
</section>

<section class="cta" id="cta">
  <div class="cta-grid" aria-hidden="true"></div>
  <svg class="cta-traces" id="ctaTraces" aria-hidden="true"></svg>
  <div class="cta-spot" aria-hidden="true"></div>
  <div class="wrap cta-in">
    <span class="label rv">Start here</span>
    <h2 class="cta-h rv">
      <span class="w" style="--i:0">Start</span> <span class="w" style="--i:1">researching</span> <span class="w" style="--i:2">funds</span> <span class="w" style="--i:3">with</span>
      <span class="cta-soft"><span class="w" style="--i:4">evidence,</span> <span class="w" style="--i:5">not</span> <span class="w" style="--i:6">headlines</span></span>
    </h2>
    <p class="cta-p rv" style="--d:.22s">Open the platform, pick a fund or build a portfolio, and see the method behind every number.</p>
    <div class="btns rv" style="--d:.3s">
      <a href="/overview" class="btn btn-primary magnet">Launch the platform <svg class="icon" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>
      <a href="/funds" class="btn btn-ghost magnet">Browse funds</a>
    </div>
    <ul class="cta-facts rv" style="--d:.4s">
      <li><b>Four</b> checks on every number</li>
      <li><b>Five</b> limitations, listed</li>
      <li><b>Versioned</b> methods, shown with results</li>
    </ul>
  </div>
</section>

</main>

<footer>
  <div class="wrap">
    <div class="foot-grid">
      <div>
        <div class="brand"><span class="brand-logo"><img class="lg-dark" src="/brand/qs-logo-dark.png" alt="" /><img class="lg-light" src="/brand/qs-logo-light.png" alt="" /></span><span><span class="brand-name">QuantSynthica</span><span class="brand-sub">MUTUAL FUNDS</span></span></div>
        <p>Quantitative research for Indian mutual funds.</p>
      </div>
      <div><h5>Platform</h5><ul><li><a href="/overview">Market overview</a></li><li><a href="/funds">Fund explorer</a></li><li><a href="/screener">Screener</a></li><li><a href="/comparison">Comparison</a></li><li><a href="/coverage">Data coverage</a></li></ul></div>
      <div><h5>Analysis</h5><ul><li><a href="/performance">Performance</a></li><li><a href="/risk">Risk</a></li><li><a href="/amc">AMC intelligence</a></li></ul></div>
      <div><h5>Research lab</h5><ul><li><a href="/quant/scoring">Fund scoring</a></li><li><a href="/quant/factors">Factor research</a></li><li><a href="/quant/regimes">Regimes</a></li><li><a href="/quant/backtesting">Backtesting</a></li></ul></div>
      <div><h5>Portfolios</h5><ul><li><a href="/portfolio/builder">Builder</a></li><li><a href="/portfolio/optimization">Optimization</a></li><li><a href="/portfolio/sip-swp">SIP / SWP</a></li><li><a href="/portfolio/stress-testing">Stress testing</a></li></ul></div>
    </div>
    <div class="foot-bottom">
      <span>Research tool, not investment advice. Past performance does not indicate future results.</span>
      <span>Mutual fund investments are subject to market risks. Times in IST.</span>
    </div>
  </div>
</footer>
`;
}
