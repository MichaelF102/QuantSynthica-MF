import { useId } from "react";

/**
 * QS monogram: stroked Q and S cut by a rising swoosh. Strokes above the swoosh use currentColor,
 * strokes below use the brand gradient #1D4ED8 -> #38BDF8 (DESIGN.md §11).
 * NOTE: redrawn from the written description; replace with the original QSLogoMark.tsx / icon.svg when available.
 */
export function QSLogoMark({ className = "h-8 w-[51px] text-slate-200" }: { className?: string }) {
  const id = useId().replace(/:/g, "");
  const letters = (
    <g fill="none" strokeWidth={13} strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="32" cy="38" rx="21" ry="26" />
      <path d="M44 52 L58 68" />
      <path d="M118 22 C100 6 76 14 82 32 C86 44 114 42 114 56 C114 72 88 76 72 62" />
    </g>
  );
  return (
    <svg viewBox="0 0 128 80" className={className} role="img" aria-label="QuantSynthica">
      <defs>
        <linearGradient id={`g${id}`} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#1D4ED8" />
          <stop offset="1" stopColor="#38BDF8" />
        </linearGradient>
        <clipPath id={`up${id}`}><path d="M0 0 H128 V30 L0 64 Z" /></clipPath>
        <clipPath id={`lo${id}`}><path d="M0 64 L128 30 V80 H0 Z" /></clipPath>
      </defs>
      <g clipPath={`url(#up${id})`} stroke="currentColor">{letters}</g>
      <g clipPath={`url(#lo${id})`} stroke={`url(#g${id})`}>{letters}</g>
    </svg>
  );
}
