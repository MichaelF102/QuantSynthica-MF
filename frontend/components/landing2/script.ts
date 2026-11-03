/* eslint-disable @typescript-eslint/no-explicit-any */
/* Behaviour of the landing page: scroll effects, reveals and the interactive instruments.
   initLanding() wires everything to the rendered markup under `root` and returns a cleanup function that removes
   every listener, observer and timer and restores the original markup, so React Strict Mode (which runs effects twice) is safe. */

const NS = "http://www.w3.org/2000/svg";

export function initLanding(root: HTMLElement, navigate: (href: string) => void): () => void {
  const original = root.innerHTML;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cleanups: (() => void)[] = [];
  const timeouts = new Set<number>();
  let alive = true;

  const $ = <T extends Element = HTMLElement>(s: string) => root.querySelector<T>(s);
  const byId = (id: string) => root.querySelector<HTMLElement>("#" + id)!;
  const $$ = (s: string) => [...root.querySelectorAll<HTMLElement>(s)];
  const on = (t: EventTarget, ev: string, fn: any, o?: any) => { t.addEventListener(ev, fn, o); cleanups.push(() => t.removeEventListener(ev, fn, o)); };
  const watch = (cb: IntersectionObserverCallback, opts?: IntersectionObserverInit) => { const o = new IntersectionObserver(cb, opts); cleanups.push(() => o.disconnect()); return o; };
  const every = (fn: () => void, ms: number) => { const id = window.setInterval(fn, ms); cleanups.push(() => clearInterval(id)); return id; };
  const after = (fn: () => void, ms: number) => { const id = window.setTimeout(() => { timeouts.delete(id); fn(); }, ms); timeouts.add(id); return id; };
  const el = (tag: string, attrs: Record<string, any> = {}, parent?: Element) => {
    const e = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, String(v)));
    parent?.appendChild(e);
    return e as SVGElement;
  };
  /** Runs `fn` once when `target` is first at least `threshold` visible. */
  const once = (target: Element, fn: () => void, threshold = 0.3) => {
    const o = watch((en) => { if (en[0].isIntersecting) { fn(); o.disconnect(); } }, { threshold });
    o.observe(target);
  };

  if (!reduce) { document.documentElement.style.scrollBehavior = "smooth"; cleanups.push(() => { document.documentElement.style.scrollBehavior = ""; }); }

  /* Same-site links become client-side navigations */
  on(root, "click", (e: MouseEvent) => {
    const a = (e.target as Element).closest?.("a[href]") as HTMLAnchorElement | null;
    if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    const href = a.getAttribute("href") ?? "";
    if (href.startsWith("/") && !href.startsWith("//")) { e.preventDefault(); navigate(href); }
  });

  /* Theme: dark by default, light on request; remembered when storage is allowed */
  (() => {
    const btn = byId("themeToggle");
    const read = () => { try { return localStorage.getItem("qs-theme"); } catch { return null; } };
    const write = (v: string) => { try { localStorage.setItem("qs-theme", v); } catch { /* storage unavailable */ } };
    const apply = (t: string) => { root.dataset.theme = t; btn.textContent = t === "light" ? "Dark" : "Light"; };
    apply(read() === "light" ? "light" : "dark");
    on(btn, "click", () => { const next = root.dataset.theme === "light" ? "dark" : "light"; apply(next); write(next); });
  })();

  /* Mobile menu */
  const nav = byId("nav"), burger = byId("burger"), menu = byId("mobileMenu");
  const setMenu = (open: boolean) => { menu.classList.toggle("open", open); burger.setAttribute("aria-expanded", String(open)); };
  on(burger, "click", () => setMenu(!menu.classList.contains("open")));
  menu.querySelectorAll("a").forEach((a) => on(a, "click", () => setMenu(false)));
  on(document, "keydown", (e: KeyboardEvent) => { if (e.key === "Escape") setMenu(false); });

  /* Scroll: progress bar, hero arc, arc hand-off into the KPI section, pipeline fill, active nav link */
  const progress = byId("progress"), pipeFill = byId("pipeFill"), eco = byId("ecosystem"), kpi = byId("kpiScroll");
  const orb = $(".hero-orb");
  const navLinks = $$("[data-nav]");
  const sections = navLinks.map((a) => ({ id: a.dataset.nav!, el: byId(a.dataset.nav!) }));
  const onScroll = () => {
    const y = window.scrollY, max = document.documentElement.scrollHeight - innerHeight;
    progress.style.transform = `scaleX(${max > 0 ? y / max : 0})`;
    nav.classList.toggle("scrolled", y > 24);
    kpi.style.setProperty("--arc", (160 * (reduce ? 0 : Math.min(1, Math.max(0, kpi.getBoundingClientRect().top / (innerHeight * 0.8))))).toFixed(1) + "px");
    if (!reduce && orb) {
      const hy = Math.min(y, innerHeight * 1.5);
      (orb as HTMLElement).style.transform = `translate3d(0, ${(hy * 0.45).toFixed(1)}px, 0) scale(${(1 - hy * 0.00006).toFixed(4)})`;
      (orb as HTMLElement).style.opacity = Math.max(0, 1 - hy / (innerHeight * 1.1)).toFixed(3);
    }
    const er = eco.getBoundingClientRect();
    const p = Math.min(1, Math.max(0, (innerHeight * 0.7 - er.top) / (er.height * 0.8)));
    pipeFill.style.transform = `scaleX(${p})`;
    $$(".pipe-step").forEach((s, i) => s.classList.toggle("on", p >= (i + 0.5) / 6));
    let current: string | null = null;
    sections.forEach((s) => { const r = s.el.getBoundingClientRect(); if (r.top <= innerHeight * 0.35 && r.bottom > innerHeight * 0.35) current = s.id; });
    navLinks.forEach((a) => a.classList.toggle("active", a.dataset.nav === current));
  };
  let ticking = false;
  const request = () => { if (!ticking) { ticking = true; requestAnimationFrame(() => { ticking = false; if (alive) onScroll(); }); } };
  on(window, "scroll", request, { passive: true });
  on(window, "resize", onScroll);
  onScroll();

  /* Reveal on scroll */
  const rv = watch((entries) => entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("in"); rv.unobserve(en.target); } }), { threshold: 0.18, rootMargin: "0px 0px -6% 0px" });
  $$(".rv, .cell, .spark, .ledger").forEach((e) => rv.observe(e));

  /* Spotlight on ecosystem cells and magnetic buttons */
  $$("[data-spot]").forEach((cell) => on(cell, "mousemove", (e: MouseEvent) => {
    const r = cell.getBoundingClientRect();
    cell.style.setProperty("--x", e.clientX - r.left + "px"); cell.style.setProperty("--y", e.clientY - r.top + "px");
  }));
  if (!reduce && matchMedia("(pointer: fine)").matches) {
    $$(".btn-primary, .magnet").forEach((b) => {
      on(b, "mousemove", (e: MouseEvent) => { const r = b.getBoundingClientRect(); b.style.transform = `translate(${((e.clientX - r.left - r.width / 2) * 0.18).toFixed(1)}px, ${((e.clientY - r.top - r.height / 2) * 0.28).toFixed(1)}px)`; });
      on(b, "mouseleave", () => { b.style.transform = ""; });
    });
  }

  /* Typewriter answer in the ecosystem card */
  (() => {
    const target = byId("typed");
    const text = "Returns are computed from official NAV records over the period you pick, ranked against true category peers.";
    if (reduce) { target.textContent = text; return; }
    once(target, () => {
      let i = 0;
      const id = every(() => { target.textContent = text.slice(0, ++i); if (i >= text.length) clearInterval(id); }, 28);
    }, 0.6);
  })();

  /* KPI scroll: figures count with scroll progress through a pinned sequence */
  (() => {
    const rows = $$(".kli");
    const kv = byId("kfV"), ku = byId("kfU"), kk = byId("kfK"), kn = byId("kfN"), ksrc = byId("kfSrc"), prog = byId("kfProg");
    const mq = matchMedia("(max-width: 880px)");
    rows.forEach((r) => { if (r.dataset.kind === "dots") { const box = r.querySelector(".kli-dots")!; for (let i = 0; i < +r.dataset.v!; i++) box.appendChild(document.createElement("i")); } });
    const fmt = (v: number, dec: number) => (dec ? v.toFixed(dec) : Math.round(v).toLocaleString("en-IN"));
    const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
    const fillDots = (r: HTMLElement, f: number) => { const d = r.querySelectorAll(".kli-dots i"); const k = Math.round(f * d.length); d.forEach((x, i) => x.classList.toggle("on", i < k)); };
    const show = (a: HTMLElement, f: number) => {
      kk.textContent = a.querySelector(".kli-k")!.textContent;
      kv.textContent = a.dataset.na ? "—" : fmt(+a.dataset.v! * f, +(a.dataset.dec || 0));
      ku.textContent = a.dataset.na ? "" : a.dataset.unit || "";
      kn.textContent = a.dataset.note ?? ""; ksrc.textContent = a.dataset.src ?? "";
    };
    let staticDone = false;
    const update = () => {
      if (reduce || mq.matches) {
        if (staticDone) return;
        staticDone = true;
        rows.forEach((r) => { r.classList.remove("act"); r.style.setProperty("--f", "1"); if (r.dataset.kind === "dots") fillDots(r, 1); });
        show(rows[0], 1); return;
      }
      staticDone = false;
      const rect = kpi.getBoundingClientRect(), total = kpi.offsetHeight - innerHeight;
      const p = Math.min(1, Math.max(0, -rect.top / total)), N = rows.length, pos = p * N, idx = Math.min(N - 1, Math.floor(pos));
      const e = easeOut(Math.min(1, (pos - idx) / 0.7));
      rows.forEach((r, i) => {
        const st = i < idx ? 1 : i === idx ? e : 0;
        r.style.setProperty("--f", st.toFixed(3)); if (r.dataset.kind === "dots") fillDots(r, st); r.classList.toggle("act", i === idx);
      });
      show(rows[idx], e); prog.style.width = (p * 100).toFixed(2) + "%";
    };
    let t = false;
    const req = () => { if (!t) { t = true; requestAnimationFrame(() => { t = false; if (alive) update(); }); } };
    on(window, "scroll", req, { passive: true }); on(window, "resize", req);
    update();
  })();

  /* Nav pill that follows the section in view; ecosystem pipeline pulse; honeycomb lean */
  (() => {
    const links = $(".links");
    if (links) {
      const pill = document.createElement("span"); pill.className = "nav-pill"; links.prepend(pill);
      const items = [...links.querySelectorAll<HTMLElement>("a[data-nav]")];
      const place = (l: HTMLElement | null) => { if (!l) { pill.classList.remove("on"); return; } pill.style.width = l.offsetWidth + "px"; pill.style.transform = `translate(${l.offsetLeft}px, 0)`; pill.classList.add("on"); };
      const o = watch((en) => en.forEach((e) => { if (e.isIntersecting) place(items.find((l) => l.dataset.nav === e.target.id) ?? null); }), { rootMargin: "-45% 0px -50% 0px" });
      items.forEach((l) => { const t = byId(l.dataset.nav!); if (t) o.observe(t); });
    }
    const pipe = byId("pipe");
    const steps = [...pipe.querySelectorAll<HTMLElement>(".pipe-step")];
    const dots = steps.map((s) => s.querySelector<HTMLElement>(".dot")!);
    const pp = document.createElement("span"); pp.className = "pp"; pipe.appendChild(pp);
    const centre = (e: HTMLElement) => { const r = e.getBoundingClientRect(), b = pipe.getBoundingClientRect(); return { x: r.left - b.left + r.width / 2, y: r.top - b.top + r.height / 2 }; };
    const pulse = () => {
      if (reduce) return;
      const a = centre(dots[0]), z = centre(dots[dots.length - 1]);
      pp.animate([{ transform: `translate(${a.x}px, ${a.y}px)`, opacity: 0 }, { transform: `translate(${a.x}px, ${a.y}px)`, opacity: 1, offset: 0.05 }, { transform: `translate(${z.x}px, ${z.y}px)`, opacity: 1, offset: 0.9 }, { transform: `translate(${z.x}px, ${z.y}px)`, opacity: 0 }], { duration: 2200, easing: "linear" });
    };
    let timer = 0;
    const po = watch((en) => { if (en[0].isIntersecting) { pulse(); if (!timer) timer = every(pulse, 2800); } else if (timer) { clearInterval(timer); timer = 0; } }, { threshold: 0.4 });
    po.observe(pipe);
    steps.forEach((s, i) => { on(s, "mouseenter", () => steps.forEach((x, j) => x.classList.toggle("lin", j <= i))); on(s, "mouseleave", () => steps.forEach((x) => x.classList.remove("lin"))); });
    if (!reduce) $$(".hive .tile").forEach((t) => {
      on(t, "mousemove", (e: MouseEvent) => { const r = t.getBoundingClientRect(); t.style.setProperty("--tx", (((e.clientX - (r.left + r.width / 2)) / r.width) * 6).toFixed(1) + "px"); t.style.setProperty("--ty", (((e.clientY - (r.top + r.height / 2)) / r.height) * 6).toFixed(1) + "px"); });
      on(t, "mouseleave", () => { t.style.setProperty("--tx", "0px"); t.style.setProperty("--ty", "0px"); });
    });
  })();

  /* Hover pie: five slices linked to their reveal cards */
  (() => {
    const svg = byId("pie").querySelector<SVGElement>(".pie")!;
    const cards = $$(".pie-card");
    const cx = 170, cy = 170, R = 160;
    const colors = ["#6aa8ff", "#2dd4bf", "#7dd3fc", "#e5b35c", "#a3e635"], names = ["Weights", "Peer", "Trust", "Clusters", "Backtests"];
    const slices: SVGElement[] = [];
    const pt = (deg: number, r: number) => [cx + r * Math.cos((deg * Math.PI) / 180), cy + r * Math.sin((deg * Math.PI) / 180)];
    for (let i = 0; i < 5; i++) {
      const a0 = -90 + i * 72, a1 = a0 + 72, am = (a0 + a1) / 2;
      const [x0, y0] = pt(a0, R), [x1, y1] = pt(a1, R);
      const g = el("g", { class: "pie-slice", tabindex: 0 }, svg);
      g.style.setProperty("--dx", (12 * Math.cos((am * Math.PI) / 180)).toFixed(1) + "px"); g.style.setProperty("--dy", (12 * Math.sin((am * Math.PI) / 180)).toFixed(1) + "px");
      el("path", { d: `M ${cx} ${cy} L ${x0.toFixed(2)} ${y0.toFixed(2)} A ${R} ${R} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)} Z`, fill: colors[i] }, g);
      const [lx, ly] = pt(am, R * 0.62);
      const label = el("text", { class: "lbl", x: lx.toFixed(1), y: ly.toFixed(1), "text-anchor": "middle", "dominant-baseline": "middle" }, g); label.textContent = names[i];
      slices.push(g);
      on(g, "mouseenter", () => activate(i)); on(g, "focus", () => activate(i));
    }
    cards.forEach((c, i) => c.querySelectorAll<HTMLElement>(".pie-points").forEach((ul) => ul.style.setProperty("--c", colors[i])));
    el("circle", { cx, cy, r: 58, class: "pie-hub" }, svg);
    const hubN = el("text", { class: "pie-hub-n", x: cx, y: cy - 4, "text-anchor": "middle" }, svg);
    const hubL = el("text", { class: "pie-hub-l", x: cx, y: cy + 22, "text-anchor": "middle" }, svg);
    function activate(i: number) {
      svg.classList.add("is-hover");
      slices.forEach((s, j) => s.classList.toggle("on", j === i)); cards.forEach((c, j) => c.classList.toggle("on", j === i));
      hubN.textContent = "0" + (i + 1); hubL.textContent = names[i];
    }
    on(svg, "mouseleave", () => svg.classList.remove("is-hover"));
    activate(0);
  })();

  /* Risk compass: watch-dial build, quadrant selection and detail panel */
  (() => {
    const svg = $<SVGElement>(".compass-svg")!;
    const cx = 200, cy = 200, R = 142, r1 = 58, dotR = 98, codeR = 122;
    const cats = [
      { name: "Returns", code: "RET", color: "var(--q-ret)", desc: "How the fund grew over every window, from one month to ten years.", items: [["Trailing 1M to 10Y", "%"], ["Calendar year", "%"], ["Rolling 1Y, 3Y, 5Y", "% p.a."], ["CAGR", "% p.a."], ["Positive-month share", "%"]] },
      { name: "Risk", code: "RISK", color: "var(--q-risk)", desc: "How far the fund swung, and how deep and how long its falls were.", items: [["Volatility", "% p.a."], ["Downside deviation", "% p.a."], ["Maximum drawdown and recovery", "% · days"], ["Beta and tracking error", "ratio · %"], ["Correlation", "-1 to 1"]] },
      { name: "Risk-adjusted", code: "RAR", color: "var(--q-rar)", desc: "How much return the fund earned for each unit of risk it took.", items: [["Sharpe", "ratio"], ["Sortino", "ratio"], ["Calmar", "ratio"], ["Information ratio", "ratio"], ["Alpha", "% p.a."]] },
      { name: "Tail risk", code: "TAIL", color: "var(--q-tail)", desc: "How bad the rare, severe days were, and how the fund fell with the market.", items: [["Value at risk, 95% and 99%", "% daily"], ["Expected shortfall", "% daily"], ["Skewness", "number"], ["Excess kurtosis", "number"], ["Downside capture", "%"]] },
    ];
    const pt = (deg: number, r: number) => [cx + r * Math.cos((deg * Math.PI) / 180), cy + r * Math.sin((deg * Math.PI) / 180)];
    const defs = el("defs", {}, svg);
    const grad = el("radialGradient", { id: "ql-dialFace", cx: "50%", cy: "50%", r: "50%" }, defs);
    el("stop", { class: "face-a", offset: "0%" }, grad); el("stop", { class: "face-b", offset: "100%" }, grad);
    el("circle", { class: "case", cx, cy, r: 196 }, svg); el("circle", { class: "case-inner", cx, cy, r: 186 }, svg); el("circle", { class: "face", cx, cy, r: 184 }, svg);
    [148, 160].forEach((r) => el("circle", { class: "guill", cx, cy, r }, svg));
    for (let t = 0; t < 60; t++) {
      const a = -90 + t * 6, [x1, y1] = pt(a, t % 5 === 0 ? 166 : 175), [x2, y2] = pt(a, 180);
      const tick = el("line", { class: t % 15 === 0 ? "tick index" : t % 5 === 0 ? "tick major" : "tick", x1: x1.toFixed(1), y1: y1.toFixed(1), x2: x2.toFixed(1), y2: y2.toFixed(1) }, svg);
      tick.style.transitionDelay = (t * 0.012).toFixed(3) + "s";
    }
    const wedges: SVGElement[] = [], dotGroups: SVGElement[][] = [];
    cats.forEach((c, i) => {
      const a0 = -90 + i * 90, a1 = a0 + 90, am = a0 + 45;
      const g = el("g", { class: "wedge", tabindex: 0, role: "button", "aria-label": c.name }, svg); g.style.setProperty("--c", c.color);
      const [x0, y0] = pt(a0 + 1.5, R), [x1, y1] = pt(a1 - 1.5, R), [x2, y2] = pt(a1 - 1.5, r1), [x3, y3] = pt(a0 + 1.5, r1);
      el("path", { d: `M${x0.toFixed(2)} ${y0.toFixed(2)} A${R} ${R} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)} L${x2.toFixed(2)} ${y2.toFixed(2)} A${r1} ${r1} 0 0 0 ${x3.toFixed(2)} ${y3.toFixed(2)} Z` }, g);
      const [lx, ly] = pt(am, codeR);
      el("text", { class: "wcode", x: lx.toFixed(1), y: ly.toFixed(1), "text-anchor": "middle", "dominant-baseline": "middle" }, g).textContent = c.code;
      const dg = el("g", {}, g), dots: SVGElement[] = [], n = c.items.length;
      c.items.forEach((_, k) => {
        const [dx, dy] = pt(n > 1 ? a0 + 18 + k * (54 / (n - 1)) : am, dotR);
        const d = el("g", { class: "cdot" }, dg); d.style.transitionDelay = (k * 0.07).toFixed(2) + "s";
        el("circle", { class: "ring", cx: dx.toFixed(1), cy: dy.toFixed(1), r: 8 }, d); el("circle", { class: "core", cx: dx.toFixed(1), cy: dy.toFixed(1), r: 3.2 }, d); dots.push(d);
      });
      dotGroups.push(dots); wedges.push(g);
      on(g, "mouseenter", () => activate(i)); on(g, "focus", () => activate(i)); on(g, "click", () => activate(i));
      on(g, "keydown", (e: KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(i); } });
    });
    [-90, 0, 90, 180].forEach((a) => { const [x1, y1] = pt(a, r1), [x2, y2] = pt(a, R); el("line", { class: "sep", x1: x1.toFixed(1), y1: y1.toFixed(1), x2: x2.toFixed(1), y2: y2.toFixed(1) }, svg); });
    const seconds = el("g", { class: "seconds" }, svg); el("line", { x1: cx, y1: cy + 16, x2: cx, y2: cy - 134 }, seconds); el("circle", { cx, cy: cy + 16, r: 2.4 }, seconds);
    const needle = el("g", { class: "needle" }, svg);
    el("polygon", { class: "hand", points: `${cx},${cy - 102} ${cx + 4.2},${cy - 16} ${cx},${cy + 58} ${cx - 4.2},${cy - 16}` }, needle);
    el("polygon", { class: "hand-tip", points: `${cx},${cy - 102} ${cx + 3},${cy - 74} ${cx - 3},${cy - 74}` }, needle);
    el("circle", { class: "hub", cx, cy, r: 56 }, svg); el("circle", { class: "hub-ring", cx, cy, r: 45 }, svg);
    el("text", { class: "dial-brand", x: cx, y: cy - 30, "text-anchor": "middle" }, svg).textContent = "QUANTSYNTHICA";
    const hubN = el("text", { class: "hub-n", x: cx, y: cy + 8, "text-anchor": "middle" }, svg), hubL = el("text", { class: "hub-l", x: cx, y: cy + 26, "text-anchor": "middle" }, svg);
    const cp = byId("cp"), cpIdx = byId("cpIdx"), cpTitle = byId("cpTitle"), cpDesc = byId("cpDesc"), cpList = byId("cpList");
    const foot = document.createElement("p"); foot.className = "cp-foot"; foot.textContent = "Each value is shown with its unit and as-of date. Peer context appears on every fund page."; cp.appendChild(foot);
    function activate(i: number) {
      const c = cats[i];
      wedges.forEach((w, j) => w.classList.toggle("on", j === i)); dotGroups.forEach((ds, j) => ds.forEach((d) => d.classList.toggle("on", j === i)));
      (needle as any).style.transform = `rotate(${45 + i * 90}deg)`;
      hubN.textContent = String(i + 1).padStart(2, "0"); hubL.textContent = c.name;
      cp.style.setProperty("--c", c.color);
      cpIdx.innerHTML = `<span>Category ${String(i + 1).padStart(2, "0")} of 04</span><span>${c.code}</span>`;
      cpTitle.textContent = c.name; cpDesc.textContent = c.desc;
      cpList.innerHTML = c.items.map(([t, u], k) => `<li style="--k:${k}"><span class="n">${c.code}.${k + 1}</span><span>${t}</span><span class="u">${u}</span></li>`).join("");
      cpList.classList.remove("show"); void cpList.offsetWidth; cpList.classList.add("show");
    }
    activate(0);
  })();

  /* Portfolio desk: faders, liquid column and risk shares (an illustrative mix) */
  (() => {
    const desk = byId("desk"), chWrap = byId("channels"), column = byId("column"), totalEl = byId("total"), effEl = byId("effN");
    const presetBtns = [...desk.querySelectorAll<HTMLElement>("[data-p]")];
    const funds = [{ name: "Large cap", color: "var(--f1)", vol: 16 }, { name: "Mid cap", color: "var(--f2)", vol: 22 }, { name: "Small cap", color: "var(--f3)", vol: 28 }, { name: "Debt", color: "var(--f4)", vol: 4 }, { name: "Gold", color: "var(--f5)", vol: 14 }];
    const presets: Record<string, number[]> = { equal: [20, 20, 20, 20, 20], defensive: [25, 10, 5, 45, 15] };
    let w = presets.equal.slice(), dragging = -1;
    const setWeight = (i: number, value: number) => {
      const v = Math.max(0, Math.min(100, value)), others = w.reduce((s, x, j) => (j === i ? s : s + x), 0), rest = 100 - v;
      w = w.map((x, j) => (j === i ? v : others > 0 ? (x / others) * rest : rest / (w.length - 1)));
      presetBtns.forEach((b) => b.classList.remove("on"));
    };
    const render = (slosh: boolean) => {
      const risk = w.map((x, i) => x * funds[i].vol), riskSum = risk.reduce((a, b) => a + b, 0) || 1, sumSq = w.reduce((s, x) => s + (x / 100) ** 2, 0);
      w.forEach((x, i) => {
        const ch = chWrap.children[i] as HTMLElement, fader = ch.querySelector<HTMLElement>(".fader")!;
        fader.style.setProperty("--p", x.toFixed(2)); fader.setAttribute("aria-valuenow", String(Math.round(x)));
        ch.querySelector(".ch-val")!.textContent = Math.round(x) + "%";
        const share = (risk[i] / riskSum) * 100;
        ch.querySelector<HTMLElement>(".risk-bar i")!.style.width = share.toFixed(1) + "%"; ch.querySelector(".risk span")!.textContent = "risk " + Math.round(share) + "%";
        const layer = column.children[i] as HTMLElement; layer.style.setProperty("--h", x.toFixed(2) + "%"); layer.firstElementChild!.textContent = x > 9 ? `${funds[i].name} ${Math.round(x)}%` : "";
      });
      totalEl.textContent = Math.round(w.reduce((a, b) => a + b, 0)) + "%"; effEl.textContent = (1 / sumSq).toFixed(1);
      if (slosh) { column.classList.remove("slosh"); void column.offsetWidth; column.classList.add("slosh"); }
    };
    funds.forEach((f, i) => {
      const ch = document.createElement("div"); ch.className = "ch"; ch.style.setProperty("--c", f.color);
      ch.innerHTML = `<div class="ch-name">${f.name}</div><div class="ch-val"></div><div class="fader" tabindex="0" role="slider" aria-label="${f.name} weight" aria-valuemin="0" aria-valuemax="100"><div class="ticks"></div><div class="knob"></div></div><div class="risk"><div class="risk-bar"><i></i></div><span></span></div>`;
      chWrap.appendChild(ch);
      const layer = document.createElement("div"); layer.className = "dlayer"; layer.style.setProperty("--c", f.color); layer.innerHTML = "<span></span>"; column.appendChild(layer);
      const fader = ch.querySelector<HTMLElement>(".fader")!;
      const fromPointer = (e: PointerEvent) => { const r = fader.getBoundingClientRect(); setWeight(i, ((r.bottom - e.clientY) / r.height) * 100); render(false); };
      on(fader, "pointerdown", (e: PointerEvent) => { dragging = i; fader.setPointerCapture(e.pointerId); fromPointer(e); });
      on(fader, "pointermove", (e: PointerEvent) => { if (dragging === i) fromPointer(e); });
      const release = () => { if (dragging === i) { dragging = -1; render(true); } };
      on(fader, "pointerup", release); on(fader, "pointercancel", release);
      on(fader, "keydown", (e: KeyboardEvent) => {
        const steps: Record<string, number> = { ArrowUp: 1, ArrowRight: 1, ArrowDown: -1, ArrowLeft: -1, PageUp: 5, PageDown: -5 };
        if (steps[e.key] !== undefined) { e.preventDefault(); setWeight(i, w[i] + steps[e.key]); render(true); }
        if (e.key === "Home") { e.preventDefault(); setWeight(i, 0); render(true); }
        if (e.key === "End") { e.preventDefault(); setWeight(i, 100); render(true); }
      });
      on(ch, "mouseenter", () => layer.classList.add("hot")); on(ch, "mouseleave", () => layer.classList.remove("hot"));
    });
    presetBtns.forEach((btn) => on(btn, "click", () => { w = presets[btn.dataset.p!].slice(); presetBtns.forEach((b) => b.classList.toggle("on", b === btn)); render(true); }));
    render(false);
  })();

  /* Portfolio lifecycle loop: six steps on a ring, detail panel and auto-cycle */
  (() => {
    const svg = $<SVGElement>(".loop-svg")!;
    const cx = 230, cy = 230, RR = 160;
    const steps = [
      { label: "Build", title: "Builder and analytics", color: "#6aa8ff", desc: "Weights, allocation by category and tier, risk contribution per fund, correlation and effective number of funds.", chips: ["Category allocation", "Risk contribution", "Correlation", "Effective number of funds"] },
      { label: "Optimise", title: "Optimisation", color: "#2dd4bf", desc: "Minimum variance, maximum Sharpe, risk parity, minimum CVaR and Black-Litterman, with weight, category and fund-count limits and an efficient frontier.", chips: ["Minimum variance", "Maximum Sharpe", "Risk parity", "Minimum CVaR", "Black-Litterman", "Efficient frontier"] },
      { label: "Validate", title: "Out-of-sample check", color: "#a78bfa", desc: "Each optimisation is fitted before the last twelve months and tested on them, and the page warns when equal weight did better.", chips: ["Fitted before last 12 months", "Tested on held-out data", "Equal-weight comparison"] },
      { label: "Simulate", title: "SIP, SWP and lump sum", color: "#e5b35c", desc: "Replay a plan on real NAV history, see the spread of outcomes across start dates, or run a clearly labelled hypothetical projection.", chips: ["Real NAV history", "Start-date spread", "Hypothetical, labelled"] },
      { label: "Stress", title: "Stress testing", color: "#f07a8f", desc: "How the mix behaved in the worst falls found in the data, plus beta-based market-shock illustrations.", chips: ["Worst historical falls", "Beta-based shocks"] },
      { label: "Rebalance", title: "Rebalancing", color: "#a3e635", desc: "Enter what you hold, get the buys and sells that return you to target, with transaction cost and exit-load estimates.", chips: ["Target weights", "Transaction cost", "Exit-load estimates"] },
    ];
    const pt = (deg: number, r: number) => [cx + r * Math.cos((deg * Math.PI) / 180), cy + r * Math.sin((deg * Math.PI) / 180)];
    el("circle", { class: "loop-track", cx, cy, r: RR }, svg); el("circle", { class: "loop-flow", cx, cy, r: RR }, svg); el("circle", { class: "loop-core", cx, cy, r: 96 }, svg);
    el("text", { class: "core-k", x: cx, y: cy - 34, "text-anchor": "middle" }, svg).textContent = "STEP";
    const coreN = el("text", { class: "core-n", x: cx, y: cy + 14, "text-anchor": "middle" }, svg), coreT = el("text", { class: "core-t", x: cx, y: cy + 50, "text-anchor": "middle" }, svg);
    let cur = 0, auto = true, hovering = false;
    const lp = byId("lp"), lpK = byId("lpK"), lpT = byId("lpT"), lpD = byId("lpD"), lpC = byId("lpC"), lpS = byId("lpS");
    steps.forEach(() => lpS.appendChild(document.createElement("i")));
    const nodes = steps.map((s, i) => {
      const a = -90 + i * 60, [x, y] = pt(a, RR);
      const g = el("g", { class: "node", tabindex: 0, role: "button", "aria-label": s.title }, svg); g.style.setProperty("--c", s.color); g.style.transitionDelay = (i * 0.08).toFixed(2) + "s";
      el("circle", { class: "pulse", cx: x.toFixed(1), cy: y.toFixed(1), r: 30 }, g); el("circle", { class: "nb", cx: x.toFixed(1), cy: y.toFixed(1), r: 30 }, g);
      el("text", { class: "nn", x: x.toFixed(1), y: y.toFixed(1), "text-anchor": "middle", "dominant-baseline": "middle" }, g).textContent = String(i + 1).padStart(2, "0");
      const cos = Math.cos((a * Math.PI) / 180), [lx, ly] = pt(a, RR + 52);
      el("text", { class: "nl", x: lx.toFixed(1), y: ly.toFixed(1), "text-anchor": cos > 0.2 ? "start" : cos < -0.2 ? "end" : "middle", "dominant-baseline": "middle" }, g).textContent = s.label;
      on(g, "mouseenter", () => { hovering = true; go(i); }); on(g, "mouseleave", () => { hovering = false; }); on(g, "focus", () => go(i));
      on(g, "click", () => { auto = false; go(i); });
      on(g, "keydown", (e: KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); auto = false; go(i); } });
      return g;
    });
    function go(i: number) {
      cur = i; const s = steps[i];
      nodes.forEach((n, j) => n.classList.toggle("on", j === i));
      coreN.textContent = String(i + 1).padStart(2, "0"); coreT.textContent = s.label;
      lp.style.setProperty("--c", s.color); lpK.textContent = `Step ${String(i + 1).padStart(2, "0")} of 06 · ${s.label}`; lpT.textContent = s.title; lpD.textContent = s.desc;
      lpC.innerHTML = s.chips.map((c, k) => `<span style="--k:${k}">${c}</span>`).join("");
      [...lpS.children].forEach((b, j) => b.classList.toggle("on", j <= i));
    }
    every(() => { if (auto && !hovering) go((cur + 1) % steps.length); }, 4200);
    go(0);
  })();

  /* Regime timeline: scrub an illustrative month-by-month history */
  (() => {
    const tl = byId("tl"), N = 250;
    const mulberry32 = (a: number) => () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    const rnd = mulberry32(42);
    const pick = (opts: [string, number][]) => { const r = rnd(); let acc = 0; for (const [k, p] of opts) { acc += p; if (r <= acc) return k; } return opts[opts.length - 1][0]; };
    const series = (opts: [string, number][], minD: number, maxD: number) => { const out: string[] = []; while (out.length < N) { const k = pick(opts), d = minD + Math.floor(rnd() * (maxD - minD + 1)); for (let j = 0; j < d && out.length < N; j++) out.push(k); } return out; };
    const trend = series([["Bull", 0.42], ["Sideways", 0.3], ["Bear", 0.28]], 8, 30), vol = series([["Low", 0.45], ["Normal", 0.4], ["High", 0.15]], 4, 16);
    const state = vol.map((v) => (v === "Low" ? (rnd() < 0.85 ? "Calm" : "Mixed") : v === "Normal" ? (rnd() < 0.7 ? "Mixed" : rnd() < 0.5 ? "Calm" : "Stressed") : rnd() < 0.8 ? "Stressed" : "Mixed"));
    for (let i = N - 10; i < N; i++) { trend[i] = "Bear"; vol[i] = "Low"; state[i] = "Calm"; }
    const monthLabel = (i: number) => `${2006 + Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, "0")}`;
    const lanes = [
      { key: "trend", data: trend, colors: { Bull: "#2dd4bf", Sideways: "#3b4a63", Bear: "#f07a8f" } as Record<string, string>, segs: [] as HTMLElement[] },
      { key: "vol", data: vol, colors: { Low: "#6aa8ff", Normal: "#3b4a63", High: "#e5b35c" } as Record<string, string>, segs: [] as HTMLElement[] },
      { key: "state", data: state, colors: { Calm: "#a78bfa", Mixed: "#3b4a63", Stressed: "#f07a8f" } as Record<string, string>, segs: [] as HTMLElement[] },
    ];
    lanes.forEach((lane) => {
      const track = tl.querySelector(`[data-track="${lane.key}"]`)!; let s = 0;
      for (let i = 1; i <= N; i++) if (i === N || lane.data[i] !== lane.data[s]) {
        const d = document.createElement("div"); d.className = "seg"; d.style.left = ((s / N) * 100).toFixed(3) + "%"; d.style.width = (((i - s) / N) * 100).toFixed(3) + "%";
        d.style.setProperty("--c", lane.colors[lane.data[s]]); d.dataset.s = String(s); d.dataset.e = String(i - 1); d.title = `${lane.data[s]}, ${monthLabel(s)} to ${monthLabel(i - 1)}`;
        track.appendChild(d); lane.segs.push(d); s = i;
      }
      const box = tl.querySelector(`[data-share="${lane.key}"]`); if (!box) return;
      const counts: Record<string, number> = {}; Object.keys(lane.colors).forEach((k) => (counts[k] = 0)); lane.data.forEach((v) => counts[v]++);
      const bar = document.createElement("div"); bar.className = "rc-bar"; const list = document.createElement("div"); list.className = "rc-keys";
      Object.keys(lane.colors).forEach((k) => {
        const pct = (counts[k] / N) * 100, seg = document.createElement("i"); seg.style.width = pct.toFixed(1) + "%"; seg.style.setProperty("--c", lane.colors[k]); seg.title = `${k} ${Math.round(pct)}%`; bar.appendChild(seg);
        const row = document.createElement("div"); row.className = "rc-key"; row.innerHTML = `<span style="--c:${lane.colors[k]}">${k}</span><b>${Math.round(pct)}%</b>`; list.appendChild(row);
      });
      box.append(bar, list);
    });
    const axis = byId("tlAxis");
    [2006, 2010, 2014, 2018, 2022, 2026].forEach((y) => { const sp = document.createElement("span"); sp.textContent = String(y); sp.style.left = (((y - 2006) * 12 + 0.5) / N * 100).toFixed(2) + "%"; if (y === 2006) sp.className = "first"; if (y === 2026) sp.className = "last"; axis.appendChild(sp); });
    const stack = byId("tlStack"), cursor = byId("tlCursor"), dateEl = byId("tlDate");
    const valEls: Record<string, HTMLElement> = {}; lanes.forEach((l) => (valEls[l.key] = tl.querySelector<HTMLElement>(`[data-val="${l.key}"]`)!));
    let idx = N - 1;
    const setIdx = (v: number) => {
      idx = Math.max(0, Math.min(N - 1, Math.round(v)));
      cursor.style.setProperty("--p", (((idx + 0.5) / N) * 100).toFixed(3) + "%"); dateEl.textContent = monthLabel(idx);
      stack.setAttribute("aria-valuenow", String(idx)); stack.setAttribute("aria-valuetext", monthLabel(idx));
      lanes.forEach((l) => { valEls[l.key].textContent = l.data[idx]; l.segs.forEach((e) => e.classList.toggle("on", idx >= +e.dataset.s! && idx <= +e.dataset.e!)); });
      stack.classList.add("scrub");
    };
    let raf = 0;
    const stopSweep = () => cancelAnimationFrame(raf);
    cleanups.push(stopSweep);
    const sweep = (from: number, to: number, dur: number) => {
      stopSweep(); const t0 = performance.now();
      const step = (now: number) => { const t = Math.min(1, (now - t0) / dur); setIdx(from + (to - from) * (1 - Math.pow(1 - t, 3))); if (t < 1 && alive) raf = requestAnimationFrame(step); };
      raf = requestAnimationFrame(step);
    };
    const idxFromX = (x: number) => { const r = stack.getBoundingClientRect(); return ((x - r.left) / r.width) * N - 0.5; };
    let dragging = false;
    on(stack, "pointerdown", (e: PointerEvent) => { stopSweep(); dragging = true; stack.setPointerCapture(e.pointerId); setIdx(idxFromX(e.clientX)); });
    on(stack, "pointermove", (e: PointerEvent) => { if (dragging) setIdx(idxFromX(e.clientX)); });
    on(stack, "pointerup", () => { dragging = false; }); on(stack, "pointercancel", () => { dragging = false; });
    on(stack, "keydown", (e: KeyboardEvent) => {
      const steps: Record<string, number> = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 12, PageDown: -12 };
      if (steps[e.key] !== undefined) { e.preventDefault(); stopSweep(); setIdx(idx + steps[e.key]); }
      if (e.key === "Home") { e.preventDefault(); stopSweep(); setIdx(0); }
      if (e.key === "End") { e.preventDefault(); stopSweep(); setIdx(N - 1); }
    });
    on(byId("tlReplay"), "click", () => sweep(0, N - 1, 3600));
    setIdx(N - 1);
    once(tl, () => { if (!reduce) sweep(0, N - 1, 3600); }, 0.35);
  })();

  /* Assistant: replay a sample session (question, tool calls, grounded answer) */
  (() => {
    const ai = byId("ai"), q = byId("aiQ"), ans = byId("aiAns"), verify = byId("aiVerify"), trace = byId("aiTrace"), replay = byId("aiReplay");
    const QUESTION = "How risky is <fund name>?";
    const rows = [...trace.querySelectorAll<HTMLElement>(".trow")], calls = [...trace.querySelectorAll<HTMLElement>(".tcall")];
    const SEG: (string | { c: number; v: string })[] = ["Over three years, the fund's volatility is ", { c: 1, v: "14.2%" }, ". Its worst peak-to-trough fall was ", { c: 2, v: "-18.6%" }, ", and its Sharpe ratio is ", { c: 3, v: "0.84" }, " against a proxy risk-free rate. These describe past behaviour and do not predict returns."];
    const tokens: HTMLElement[] = [];
    SEG.forEach((seg) => {
      if (typeof seg === "string") {
        seg.split(/(\s+)/).forEach((part) => {
          if (!part) return;
          if (/^\s+$/.test(part)) { ans.appendChild(document.createTextNode(part)); return; }
          const s = document.createElement("span"); s.className = "tk"; s.textContent = part; ans.appendChild(s); tokens.push(s);
        });
      } else {
        const wrap = document.createElement("span"); wrap.className = "tk";
        const c = document.createElement("span"); c.className = "cite"; c.dataset.c = String(seg.c); c.tabIndex = 0; c.textContent = seg.v;
        const sup = document.createElement("sup"); sup.textContent = String(seg.c); c.appendChild(sup); wrap.appendChild(c); ans.appendChild(wrap); tokens.push(wrap);
        const linked = ai.querySelectorAll(`[data-n="${seg.c}"]`), hl = (v: boolean) => linked.forEach((r) => r.classList.toggle("hl", v));
        on(c, "mouseenter", () => hl(true)); on(c, "mouseleave", () => hl(false)); on(c, "focus", () => hl(true)); on(c, "blur", () => hl(false));
      }
    });
    ai.querySelectorAll<HTMLElement>(".notes .fn").forEach((f) => tokens.push(f));
    calls.forEach((c) => on(c, "click", () => { const open = c.parentElement!.classList.toggle("open"); c.setAttribute("aria-expanded", String(open)); }));
    const clearTimers = () => { timeouts.forEach(clearTimeout); timeouts.clear(); };
    cleanups.push(clearTimers);
    const reset = () => { clearTimers(); q.textContent = ""; ai.classList.remove("fin"); rows.forEach((r) => r.classList.remove("on", "hl", "open")); calls.forEach((c) => c.setAttribute("aria-expanded", "false")); tokens.forEach((t) => t.classList.remove("on")); verify.classList.remove("on"); };
    const finish = () => { q.textContent = QUESTION; rows.forEach((r) => r.classList.add("on")); tokens.forEach((t) => t.classList.add("on")); verify.classList.add("on"); ai.classList.add("fin"); };
    const run = () => {
      reset(); if (reduce) { finish(); return; }
      let t = 300;
      [...QUESTION].forEach((ch, i) => after(() => { q.textContent += ch; }, t + i * 38)); t += QUESTION.length * 38 + 350;
      rows.forEach((r) => { after(() => r.classList.add("on"), t); t += 750; }); t += 200;
      tokens.forEach((tk, i) => after(() => tk.classList.add("on"), t + i * 40)); t += tokens.length * 40 + 200;
      after(() => { verify.classList.add("on"); ai.classList.add("fin"); }, t);
    };
    on(replay, "click", run); reset(); once(ai, run, 0.3);
  })();

  /* Methodology filter funnel: data passes four screens; limitations leak outside */
  (() => {
    const svg = byId("fnSvg"), stage = byId("fnStage"), outlet = byId("fnOut");
    const TOP = 40, BOT = 560, END = 620, XL0 = 60, XR0 = 540, XL1 = 250, XR1 = 350, SCR = [150, 250, 350, 450], COL = ["#6aa8ff", "#2dd4bf", "#a78bfa", "#9aa6b8"];
    const xL = (y: number) => XL0 + ((XL1 - XL0) * (y - TOP)) / (BOT - TOP), xR = (y: number) => XR0 + ((XR1 - XR0) * (y - TOP)) / (BOT - TOP);
    const rules = $$("#fnRules li"), leaks = $$("#fnLeaks li");
    const DUR = 2600, GAP = 380, NDROP = 8;
    el("polygon", { points: `${XL0},${TOP} ${XR0},${TOP} ${XR1},${BOT} ${XL1},${BOT}`, class: "fn-body" }, svg); el("rect", { x: XL1, y: BOT, width: XR1 - XL1, height: END - BOT, class: "fn-pipe" }, svg);
    const screens = SCR.map((y, k) => ({ s: el("line", { x1: xL(y), y1: y, x2: xR(y), y2: y, class: "fn-screen", stroke: COL[k] }, svg), hit: el("line", { x1: xL(y), y1: y, x2: xR(y), y2: y, class: "fn-hit" }, svg) }));
    const LEAK = [{ s: 0, side: -1 }, { s: 1, side: 1 }, { s: 1, side: -1 }, { s: 2, side: 1 }, { s: 3, side: -1 }];
    const traces = LEAK.map((L) => { const y = SCR[L.s], x0 = L.side < 0 ? xL(y) - 2 : xR(y) + 2; return el("path", { d: `M${x0} ${y} Q${x0 + L.side * 30} ${y + 40} ${x0 + L.side * 75} ${y + 120}`, class: "fn-trace" }, svg); });
    let inView = false, anims: Animation[] = [];
    const myTimers = new Set<number>();
    const later = (fn: () => void, ms: number) => { const id = window.setTimeout(() => { myTimers.delete(id); fn(); }, ms); myTimers.add(id); };
    cleanups.push(() => { myTimers.forEach(clearTimeout); anims.forEach((a) => a.cancel()); });
    const drop = (x0: number, y0: number, x1: number, y1: number, dur: number, delay: number, kind: string) => {
      const d = el("circle", { r: kind === "leak" ? 3.5 : kind === "amb" ? 2.2 : 3, class: `fn-drop ${kind}`, cx: 0, cy: 0 }, svg);
      const kf = kind === "leak" ? [{ transform: `translate(${x0}px, ${y0}px)`, opacity: 1 }, { transform: `translate(${x1}px, ${y1}px)`, opacity: 0 }]
        : [{ transform: `translate(${x0}px, ${y0}px)`, opacity: 0.9, offset: 0 }, { transform: `translate(${x1}px, ${y1}px)`, opacity: 0.9, offset: 0.85 }, { transform: `translate(${x1}px, ${y1}px)`, opacity: 0, offset: 1 }];
      const a = d.animate(kf, { duration: dur, delay, easing: kind === "leak" ? "ease-in" : "linear", fill: "forwards" }); anims.push(a);
      a.onfinish = () => { d.remove(); anims = anims.filter((x) => x !== a); };
    };
    const reset = () => { myTimers.forEach(clearTimeout); myTimers.clear(); anims.forEach((a) => a.cancel()); anims = []; svg.querySelectorAll(".fn-drop").forEach((d) => d.remove()); rules.forEach((r) => r.classList.remove("lit")); leaks.forEach((l) => l.classList.remove("lit")); outlet.classList.remove("lit"); screens.forEach((o) => o.s.classList.remove("hit")); };
    const lightAll = () => { rules.forEach((r) => r.classList.add("lit")); leaks.forEach((l) => l.classList.add("lit")); outlet.classList.add("lit"); };
    const play = () => {
      reset(); if (reduce) { lightAll(); return; }
      for (let i = 0; i < NDROP; i++) {
        const start = 300 + i * GAP; drop(300, TOP, 300, END, DUR, start, "data");
        SCR.forEach((y, k) => { const at = start + (DUR * (y - TOP)) / (END - TOP); later(() => { screens[k].s.classList.add("hit"); later(() => screens[k].s.classList.remove("hit"), 320); }, at); if (i === 0) later(() => rules[k].classList.add("lit"), at); });
      }
      LEAK.forEach((L, k) => {
        const y = SCR[L.s], at = 300 + Math.min(k + 1, NDROP - 1) * GAP + (DUR * (y - TOP)) / (END - TOP), x0 = L.side < 0 ? xL(y) - 2 : xR(y) + 2;
        later(() => drop(x0, y, x0 + L.side * 75, y + 120, 1400, 0, "leak"), at); later(() => leaks[k].classList.add("lit"), at + 1000);
      });
      later(() => outlet.classList.add("lit"), 300 + (NDROP - 1) * GAP + DUR + 200);
    };
    const focusRule = (k: number) => { rules[k].classList.add("hov"); screens[k].s.classList.add("focus"); }, blurRule = (k: number) => { rules[k].classList.remove("hov"); screens[k].s.classList.remove("focus"); };
    rules.forEach((r, k) => { on(r, "mouseenter", () => focusRule(k)); on(r, "mouseleave", () => blurRule(k)); });
    screens.forEach((o, k) => { on(o.hit, "mouseenter", () => focusRule(k)); on(o.hit, "mouseleave", () => blurRule(k)); });
    leaks.forEach((l, k) => {
      on(l, "mouseenter", () => { l.classList.add("hov"); traces[k].classList.add("on"); screens[LEAK[k].s].s.classList.add("focus"); });
      on(l, "mouseleave", () => { l.classList.remove("hov"); traces[k].classList.remove("on"); screens[LEAK[k].s].s.classList.remove("focus"); });
    });
    if (!reduce) {
      on(stage, "mousemove", (e: MouseEvent) => { const r = stage.getBoundingClientRect(); stage.style.setProperty("--ry", `${(((e.clientX - r.left) / r.width - 0.5) * 6).toFixed(2)}deg`); stage.style.setProperty("--rx", `${(-((e.clientY - r.top) / r.height - 0.5) * 6).toFixed(2)}deg`); });
      on(stage, "mouseleave", () => { stage.style.setProperty("--rx", "0deg"); stage.style.setProperty("--ry", "0deg"); });
      every(() => { if (inView) drop(300, TOP, 300, END, DUR, 0, "amb"); }, 900);
    }
    watch((en) => { inView = en[0].isIntersecting; }, { threshold: 0.2 }).observe(svg);
    on(byId("fnReplay"), "click", play);
    reset(); if (reduce) lightAll(); else once(svg, play, 0.3);
  })();

  /* CTA: circuit traces and cursor spotlight */
  (() => {
    const cta = byId("cta"), svg = byId("ctaTraces"), spot = cta.querySelector<HTMLElement>(".cta-spot")!;
    const SPECS: { start: number[]; steps: [string, number][] }[] = [
      { start: [0, 0.1], steps: [["h", 0.18], ["d", 0.2], ["h", 0.26]] }, { start: [0, 0.24], steps: [["h", 0.12], ["d", 0.36], ["h", 0.24]] },
      { start: [0, 0.46], steps: [["h", 0.08], ["d", 0.62], ["h", 0.22]] }, { start: [0, 0.74], steps: [["h", 0.16], ["d", 0.86], ["h", 0.26]] },
    ];
    const pathFor = (spec: (typeof SPECS)[number], W: number, H: number, mirror: boolean) => {
      let x = spec.start[0] * W, y = spec.start[1] * H; const map = (lx: number) => (mirror ? W - lx : lx); let d = `M${map(x)} ${y}`;
      spec.steps.forEach(([type, f]) => { if (type === "h") { x = f * W; d += ` H${map(x)}`; } else { const ny = f * H; x += Math.abs(ny - y); y = ny; d += ` L${map(x)} ${y}`; } });
      return d;
    };
    const items: { spec: (typeof SPECS)[number]; mirror: boolean; base: SVGElement; run: SVGElement }[] = [];
    SPECS.forEach((spec) => [false, true].forEach((mirror) => {
      const base = el("path", { class: "base draw", pathLength: 1 }, svg), run = el("path", { class: "run", pathLength: 1 }, svg);
      run.style.animationDelay = `${(items.length * 0.45).toFixed(2)}s`; items.push({ spec, mirror, base, run });
    }));
    const layout = () => { const r = svg.getBoundingClientRect(); if (!r.width || !r.height) return; items.forEach((it) => { const d = pathFor(it.spec, r.width, r.height, it.mirror); it.base.setAttribute("d", d); it.run.setAttribute("d", d); }); };
    layout(); on(window, "resize", layout);
    once(cta, () => svg.classList.add("in"), 0.25); if (reduce) svg.classList.add("in");
    if (!reduce) on(cta, "mousemove", (e: MouseEvent) => { const r = cta.getBoundingClientRect(); spot.style.setProperty("--x", `${e.clientX - r.left}px`); spot.style.setProperty("--y", `${e.clientY - r.top}px`); });
  })();

  return () => {
    alive = false;
    timeouts.forEach(clearTimeout); timeouts.clear();
    cleanups.forEach((fn) => fn());
    root.innerHTML = original;
  };
}
