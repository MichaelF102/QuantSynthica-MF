import { api } from "@/lib/api";
import { Screener, type ScreenState } from "@/components/funds/Screener";

type SP = Promise<Record<string, string | string[] | undefined>>;

function parseState(raw: string | undefined): Partial<ScreenState> | undefined {
  if (!raw) return undefined;
  try {
    const s = JSON.parse(raw);
    return s && typeof s === "object" ? s : undefined;
  } catch {
    return undefined;
  }
}

export default async function ScreenerPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const s = Array.isArray(sp.s) ? sp.s[0] : sp.s;
  const [fields, options] = await Promise.all([api.fields(), api.filterOptions()]);
  return <Screener fields={fields} options={options} initial={parseState(s)} />;
}
