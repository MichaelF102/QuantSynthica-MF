import Link from "next/link";
import { Search } from "lucide-react";
import { EmptyState, PageHeader, Panel, btnPrimary, inputCls } from "@/components/ui/ui";
import { api } from "@/lib/api";
import { crore, dash, fmtInt, fmtPrice, pct, tone } from "@/lib/format";

type SP = Promise<Record<string, string | string[] | undefined>>;
const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
const TH = "py-1.5 px-2 text-[10px] font-medium uppercase tracking-wider text-muted";

const COLUMNS: { key: string; label: string; sort?: string; right?: boolean }[] = [
  { key: "name", label: "Fund", sort: "name" },
  { key: "category", label: "Category" },
  { key: "plan", label: "Plan / Option" },
  { key: "price", label: "Price", sort: "price", right: true },
  { key: "ytd", label: "YTD", sort: "ytd_return", right: true },
  { key: "r3m", label: "3M", sort: "return_3m", right: true },
  { key: "r1y", label: "1Y", sort: "return_1y", right: true },
  { key: "r3y", label: "3Y", sort: "return_3y", right: true },
  { key: "r5y", label: "5Y", sort: "return_5y", right: true },
  { key: "aum", label: "Net assets", sort: "net_assets", right: true },
];

export default async function FundsPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const page = Math.max(1, Number(first(sp.page)) || 1);
  const sort = first(sp.sort) ?? "name";
  const order = first(sp.order) === "desc" ? "desc" : "asc";
  const q = first(sp.q);
  const asset_tier = first(sp.asset_tier);
  const plan_type = first(sp.plan_type);
  const option_type = first(sp.option_type);

  const data = await api.funds({ page, page_size: 50, sort, order, q, asset_tier, plan_type, option_type });
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));

  const link = (over: Record<string, string | number | undefined>) => {
    const p = new URLSearchParams();
    const merged = { q, asset_tier, plan_type, option_type, sort, order, page, ...over };
    for (const [k, v] of Object.entries(merged)) if (v !== undefined && v !== "") p.set(k, String(v));
    return `/funds?${p.toString()}`;
  };

  return (
    <>
      <PageHeader title="Fund" accent="Explorer" subtitle="DISCOVER"
        description={`${fmtInt(data.total)} schemes · QuantSynthica market data snapshot (run ${data.ingestion_run_id ?? dash}; snapshot date unknown)`} />

      <Panel>
        <form className="flex flex-wrap items-end gap-3 text-xs" method="get" role="search">
          <label className="flex flex-col gap-1"><span className="text-muted">Search</span>
            <span className="relative flex items-center"><Search className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-muted" />
              <input name="q" defaultValue={q} placeholder="Fund or AMC" className={`${inputCls} pl-8`} /></span></label>
          <Select name="asset_tier" label="Asset tier" value={asset_tier} options={["Equity", "Debt", "Hybrid", "Other"]} />
          <Select name="plan_type" label="Plan" value={plan_type} options={["Direct", "Regular", "Institutional", "Unspecified"]} />
          <Select name="option_type" label="Option" value={option_type} options={["Growth", "IDCW", "Unspecified"]} />
          <button className={btnPrimary}>Apply</button>
          <Link href="/funds" className="px-2 py-2 text-[11px] font-medium text-accent hover:underline">Reset</Link>
        </form>
      </Panel>

      <Panel>
        {data.items.length === 0 ? (
          <EmptyState title={data.ingestion_run_id === null ? "No data ingested yet" : "No funds match these filters"}
            hint={data.ingestion_run_id === null ? "Run `make ingest` to load the fund snapshot." : "Loosen a filter or reset."} />
        ) : (
          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead><tr className="border-b border-line">
                {COLUMNS.map((c) => (
                  <th key={c.key} className={`${TH} ${c.right ? "text-right" : ""}`}>
                    {c.sort ? (
                      <Link href={link({ sort: c.sort, order: sort === c.sort && order === "asc" ? "desc" : "asc", page: 1 })} className="hover:text-strong">
                        {c.label}{sort === c.sort ? (order === "asc" ? " ▲" : " ▼") : ""}
                      </Link>
                    ) : c.label}
                  </th>
                ))}
              </tr></thead>
              <tbody className="divide-y divide-line/50">
                {data.items.map((f) => (
                  <tr key={f.id} className="transition-colors hover:bg-hover">
                    <td className="max-w-[360px] px-2 py-2">
                      <Link href={`/funds/${f.id}`} className="font-medium text-fg hover:text-accent">{f.name}</Link>
                      <div className="text-[11px] text-muted">{f.amc}</div>
                    </td>
                    <td className="px-2 py-2 text-muted">{f.category}</td>
                    <td className="px-2 py-2 text-muted">{f.plan_type} · {f.option_type}</td>
                    <td className="px-2 py-2 text-right">{fmtPrice(f.price)}</td>
                    {[f.ytd_return, f.return_3m, f.return_1y, f.return_3y, f.return_5y].map((v, i) => (
                      <td key={i} className={`px-2 py-2 text-right font-semibold ${v === null ? "text-faint" : tone(v)}`}>{pct(v)}</td>
                    ))}
                    <td className="px-2 py-2 text-right">{crore(f.net_assets)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <div className="flex items-center justify-between text-xs text-muted">
        <span className="font-mono">Page {data.page} of {pages}</span>
        <div className="flex gap-4">
          {data.page > 1 && <Link href={link({ page: data.page - 1 })} className="font-medium text-accent hover:underline">← Previous</Link>}
          {data.page < pages && <Link href={link({ page: data.page + 1 })} className="font-medium text-accent hover:underline">Next →</Link>}
        </div>
      </div>
    </>
  );
}

function Select({ name, label, value, options }: { name: string; label: string; value?: string; options: string[] }) {
  return (
    <label className="flex flex-col gap-1"><span className="text-muted">{label}</span>
      <select name={name} defaultValue={value ?? ""} className={inputCls}>
        <option value="">All</option>{options.map((o) => <option key={o}>{o}</option>)}
      </select>
    </label>
  );
}
