import { ApiStartingLoader } from "@/components/ui/ai-loader";

// Shown while a platform page waits for the API (a free-tier API can take up to a minute to wake). Fills the content area, so the navigation stays usable.
export default function Loading() {
  return <ApiStartingLoader fullscreen={false} />;
}
