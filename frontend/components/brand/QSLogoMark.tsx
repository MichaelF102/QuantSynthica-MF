/* eslint-disable @next/next/no-img-element */
/**
 * QS logo. Two renderings of the same artwork (light letters for the dark theme, dark letters for the light theme);
 * `.qs-logo-*` in globals.css shows the one that matches the `dark` class on <html>.
 */
export function QSLogoMark({ className = "h-8 w-auto" }: { className?: string }) {
  return (
    <>
      <img src="/brand/qs-logo-light.png" alt="QuantSynthica" className={`qs-logo-light ${className}`} />
      <img src="/brand/qs-logo-dark.png" alt="" aria-hidden className={`qs-logo-dark ${className}`} />
    </>
  );
}
