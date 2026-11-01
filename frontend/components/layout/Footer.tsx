export function Footer() {
  return (
    <footer data-print-hide className="mt-10 border-t border-line">
      <div className="app-container flex flex-col gap-1 py-5 text-[11px] text-faint sm:flex-row sm:items-center sm:justify-between">
        <span className="font-semibold text-muted">Quant<span className="text-accent">Synthica</span> Mutual Funds</span>
        <span>Research tool, not investment advice. Past performance does not indicate future results. Times in IST.</span>
      </div>
    </footer>
  );
}
