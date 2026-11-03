import * as React from "react";

interface LoaderProps {
  size?: number;
  /** Letters that pulse inside the ring. Keep it short (it sits in a circle). */
  text?: string;
  /** Sentence shown under the ring. */
  message?: string;
  /** Cover the whole screen (landing page) instead of filling the content area (platform pages). */
  fullscreen?: boolean;
}

/**
 * Animated ring with pulsing letters. Adapted from the supplied loader: the keyframes live in globals.css (no styled-jsx, so it also
 * works in Server Components and loading.tsx), and the colours follow the active theme (`dark` class) instead of the OS setting.
 * Used wherever a page waits for the API, which on a free host can take up to a minute to wake up.
 */
export const Component: React.FC<LoaderProps> = ({ size = 180, text = "Loading", message = "Starting the API, please wait…", fullscreen = true }) => {
  const letters = text.split("");
  return (
    <div
      role="status"
      aria-live="polite"
      className={`qs-loader flex flex-col items-center justify-center gap-6 ${fullscreen ? "fixed inset-0 z-50" : "min-h-[60vh] rounded-xl"}`}
    >
      <div className="relative flex select-none items-center justify-center font-sans text-lg font-semibold" style={{ width: size, height: size }}>
        {letters.map((letter, index) => (
          <span key={index} className="qs-loader-letter inline-block opacity-40" style={{ animationDelay: `${index * 0.1}s` }}>
            {letter}
          </span>
        ))}
        <div aria-hidden className="qs-loader-circle absolute inset-0 rounded-full" />
      </div>
      <p className="max-w-xs px-6 text-center text-sm opacity-80">
        {message}
        <span className="mt-1 block text-xs opacity-70">The first visit after a quiet period can take up to a minute.</span>
      </p>
    </div>
  );
};

/** The loader with its default message, for loading.tsx files and Suspense fallbacks. */
export function ApiStartingLoader(props: Omit<LoaderProps, "message">) {
  return <Component {...props} />;
}
