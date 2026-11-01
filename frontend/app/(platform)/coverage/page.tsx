import { Database, GitMerge, History, Layers, CalendarClock, Building2, Percent } from "lucide-react";
import { BarRow, Banner, EmptyState, PageHeader, Panel, StatTile } from "@/components/ui/ui";
import { ApiError, api, type Coverage } from "@/lib/api";
import { dash, fmtInt } from "@/lib/format";

const TH = "py-1.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted";
const STATUS_ORDER = ["confirmed", "probable", "name_only", "ambiguous", "unmapped", "not_amfi_scheme"];
const STATUS_LABEL: Record<string, string> = {
  confirmed: "Confirmed", probable: "Probable", name_only: "Name only", ambiguous: "Ambiguous", unmapped: "Unmapped", not_amfi_scheme: "Not a registered scheme",
};
const STATUS_HELP: Record<string, string> = {
  confirmed: "Name, plan and option agree and the NAV equals the official NAV on the snapshot date.",
  probable: "Strong but not exact evidence (NAV close, or exact NAV with a renamed scheme).",
  name_only: "Names agree; NAV evidence is missing or disagrees.",
  ambiguous: "More than one official scheme fits equally well; not resolved by guessing.",
  unmapped: "No acceptable official scheme found.",
  not_amfi_scheme: "Insurer-linked fund with no official mutual fund scheme record.",
};
const STATUS_COLOR: Record<string, string> = {
  confirmed: "bg-up", probable: "bg-accent", name_only: "bg-warn", ambiguous: "bg-warn", unmapped: "bg-down", not_amfi_scheme: "bg-faint",
};
const pctOf = (n: number, d: number) => (d ? `${((n / d) * 100).toFixed(1)}%` : dash);

export default async function CoveragePage() {
  let c: Coverage | null = null;
  let missing = false;
  try {
    c = await api.coverage();
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) missing = true;
    else throw e;
  }

  return (
    <>
      <PageHeader title="Data" accent="Coverage" subtitle="DATA"
        description="How much of the fund universe is linked to official scheme records and has NAV history. Analytics in later phases only reach funds counted here." />
      {missing || !c ? (
        <Panel><EmptyState icon={Database} title="Coverage report not generated yet" hint="Run `python -m app.cli.pipeline coverage` after the mapping step." /></Panel>
      ) : <Body c={c} />}
    </>
  );
}

function Body({ c }: { c: Coverage }) {
  const m = c.mapping;
  const nav = c.nav_history;
  const fam = c.families;
  const snap = c.snapshot_date;
  const statuses = m ? STATUS_ORDER.filter((s) => (m.status_counts[s] ?? 0) > 0) : [];
  const maxStatus = m ? Math.max(...statuses.map((s) => m.status_counts[s])) : 0;

  return (
    <>
      {c.note && <Banner tone="warn">{c.note}</Banner>}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <StatTile icon={Database} label="Official schemes" value={fmtInt(c.register.schemes)}
          sub={c.register.summary?.latest_nav_date ? `latest NAV ${c.register.summary.latest_nav_date}` : undefined} />
        <StatTile icon={GitMerge} label="Accepted mappings (non-insurer)" value={m ? pctOf(Math.round((m.accepted_share_non_insurer ?? 0) * m.non_insurer_schemes), m.non_insurer_schemes) : dash}
          sub={m ? `${fmtInt(m.distinct_official_codes_accepted)} distinct official codes` : undefined} />
        <StatTile icon={Percent} label="Confirmed (non-insurer)" value={m ? `${((m.confirmed_share_non_insurer ?? 0) * 100).toFixed(1)}%` : dash} sub="exact NAV on snapshot date" />
        <StatTile icon={History} label="With NAV history" value={nav ? fmtInt(nav.with_history) : dash} sub={nav ? `of ${fmtInt(nav.accepted_schemes)} accepted` : undefined} />
        <StatTile icon={History} label="≥ 3 years of history" value={nav ? fmtInt(nav.at_least_3y) : dash} sub={nav ? `≥ 5y ${fmtInt(nav.at_least_5y)} · ≥ 10y ${fmtInt(nav.at_least_10y)}` : undefined} />
        <StatTile icon={CalendarClock} label="Snapshot date (estimated)" value={snap?.estimate ?? dash}
          sub={snap?.votes ? `${fmtInt(snap.votes)} of ${fmtInt(snap.pairs_used)} funds agree` : "not determined"} />
      </div>

      {m && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <Panel icon={GitMerge} title="Mapping status" description={`${fmtInt(m.schemes_total)} source schemes, none dropped`}
              info="Each source scheme is linked to an official scheme code only when name, plan, option and NAV evidence agree. Ambiguous cases are left unresolved.">
              {statuses.map((s) => (
                <div key={s} title={STATUS_HELP[s]}>
                  <BarRow label={STATUS_LABEL[s]} value={m.status_counts[s]} max={maxStatus} text={fmtInt(m.status_counts[s])} color={STATUS_COLOR[s]} />
                </div>
              ))}
              <p className="mt-3 text-[11px] text-faint">{m.note} Slot conflicts: {m.slot_conflicts}.</p>
            </Panel>
          </div>
          <div className="lg:col-span-7">
            <Panel icon={Layers} title="By asset tier (non-insurer)" description="Share of schemes in each status">
              <div className="w-full overflow-x-auto">
                <table className="w-full border-collapse text-left text-xs">
                  <thead><tr className="border-b border-line"><th className={TH}>Tier</th>
                    {STATUS_ORDER.filter((s) => s !== "not_amfi_scheme").map((s) => <th key={s} className={`${TH} text-right`}>{STATUS_LABEL[s]}</th>)}
                    <th className={`${TH} text-right`}>Total</th></tr></thead>
                  <tbody className="divide-y divide-line/50">
                    {Object.entries(m.by_asset_tier).map(([tier, counts]) => {
                      const total = Object.values(counts).reduce((a, b) => a + b, 0);
                      return (
                        <tr key={tier} className="transition-colors hover:bg-hover">
                          <td className="px-2 py-2 font-medium text-fg">{tier}</td>
                          {STATUS_ORDER.filter((s) => s !== "not_amfi_scheme").map((s) => <td key={s} className="px-2 py-2 text-right">{pctOf(counts[s] ?? 0, total)}</td>)}
                          <td className="px-2 py-2 text-right text-muted">{fmtInt(total)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {fam && (
          <Panel icon={Layers} title="Fund families" description="Funds reach the ranking universe through their Direct-Growth class"
            info="A fund family groups the share classes of one fund. Rankings use one class per family (Direct plan, Growth option).">
            <dl className="divide-y divide-line/50 text-xs">
              {[
                ["Families (non-insurer)", fam.non_insurer_families],
                ["With an accepted mapping", fam.families_with_accepted_mapping],
                ["With a Direct-Growth class", fam.families_with_direct_growth],
                ["Direct-Growth class mapped", fam.direct_growth_mapped],
                ["…and ≥ 3 years of NAV history", fam.direct_growth_mapped_with_3y_history],
              ].map(([k, v]) => (
                <div key={k as string} className="flex justify-between py-2"><dt className="text-muted">{k}</dt><dd className="font-mono text-strong">{fmtInt(v as number)}</dd></div>
              ))}
            </dl>
          </Panel>
        )}
        {nav && (
          <Panel icon={History} title="NAV history" description="For accepted mappings">
            <dl className="divide-y divide-line/50 text-xs">
              {[
                ["Observations stored", nav.observations_total], ["Schemes with history", nav.with_history], ["Not loaded yet", nav.not_loaded],
                ["Failed to load", nav.failed], ["With quality flags", nav.with_quality_issues],
              ].map(([k, v]) => (
                <div key={k as string} className="flex justify-between py-2"><dt className="text-muted">{k}</dt><dd className="font-mono text-strong">{fmtInt(v as number)}</dd></div>
              ))}
            </dl>
            <p className="mt-3 text-[11px] text-faint">Quality flags are reported, not deleted: gaps over 10 days, daily moves over 20%, invalid or conflicting values.</p>
          </Panel>
        )}
      </div>

      {c.return_semantics && Object.keys(c.return_semantics).length > 1 && (
        <Panel icon={Percent} title="Are the reported returns current?" description="Reported returns checked against NAV-derived returns ending on the snapshot date (Growth schemes, confirmed mappings)"
          info="A return is 'current' when at least 90% of funds are within 1 percentage point of the NAV-derived value ending on the snapshot date.">
          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead><tr className="border-b border-line"><th className={TH}>Return</th><th className={`${TH} text-right`}>Funds</th>
                <th className={`${TH} text-right`}>Within 1pp of NAV-derived</th><th className={`${TH} text-right`}>Median error (pp)</th>
                <th className={TH}>Basis</th><th className={TH}>Verdict</th></tr></thead>
              <tbody className="divide-y divide-line/50">
                {Object.entries(c.return_semantics).filter(([, v]) => typeof v === "object").map(([h, v]) => {
                  const r = v as Exclude<NonNullable<Coverage["return_semantics"]>[string], string>;
                  const within = r.share_within_1pp_annualised ?? r.share_within_1pp_cumulative;
                  const err = r.median_abs_error_vs_annualised_pp ?? r.median_abs_error_vs_cumulative_pp;
                  return (
                    <tr key={h} className="transition-colors hover:bg-hover">
                      <td className="px-2 py-2 font-medium uppercase text-fg">{h}</td>
                      <td className="px-2 py-2 text-right">{fmtInt(r.funds_compared)}</td>
                      <td className="px-2 py-2 text-right">{(within * 100).toFixed(1)}%</td>
                      <td className="px-2 py-2 text-right">{err.toFixed(2)}</td>
                      <td className="px-2 py-2 text-muted">{r.closer_to ?? "cumulative"}</td>
                      <td className={`px-2 py-2 font-semibold ${r.aligned_to_snapshot ? "text-up" : "text-warn"}`}>
                        {r.aligned_to_snapshot ? "Current" : "Not aligned to snapshot date"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-[11px] text-faint">
            Returns marked not aligned were measured to earlier dates that differ by fund. Use NAV-derived returns for analysis; treat these as indicative only.
          </p>
        </Panel>
      )}

      {snap && (
        <Panel icon={CalendarClock} title="How the snapshot date is estimated">
          <p className="text-xs text-muted">{snap.method}</p>
        </Panel>
      )}

      {c.unmatched_amcs && c.unmatched_amcs.length > 0 && (
        <Panel icon={Building2} title="Source AMCs without an official match" description="Mostly insurers; reviewed manually"
          info="Add reviewed pairs to data/reference/amc_overrides.csv.">
          <ul className="flex flex-wrap gap-1.5">
            {c.unmatched_amcs.map((a) => <li key={a} className="rounded-full border border-line bg-raised px-2.5 py-0.5 text-[11px] text-fg">{a}</li>)}
          </ul>
        </Panel>
      )}
      <p className="text-[11px] text-faint">Report generated {new Date(c.generated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST.</p>
    </>
  );
}
