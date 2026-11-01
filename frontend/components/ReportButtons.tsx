"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { btnSecondary } from "@/components/ui/ui";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Downloads a PDF or Excel report built by the API from the same numbers the page shows. */
export function ReportButtons({ kind, params }: { kind: "fund" | "portfolio" | "amc"; params: Record<string, unknown> }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const get = async (fmt: "pdf" | "xlsx") => {
    setBusy(fmt); setErr(null);
    try {
      const r = await fetch(`${BASE}/api/v1/reports/${kind}.${fmt}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(params) });
      if (!r.ok) throw new Error((await r.json().catch(() => ({ detail: "Report failed" }))).detail);
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url; a.download = `qsmf-${kind}-report.${fmt}`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button onClick={() => get("pdf")} disabled={busy !== null} className={btnSecondary}><Download className="h-3.5 w-3.5" /> {busy === "pdf" ? "Preparing…" : "PDF report"}</button>
      <button onClick={() => get("xlsx")} disabled={busy !== null} className={btnSecondary}><Download className="h-3.5 w-3.5" /> {busy === "xlsx" ? "Preparing…" : "Excel report"}</button>
      {err && <span role="alert" className="text-[11px] text-down">{err}</span>}
    </div>
  );
}
