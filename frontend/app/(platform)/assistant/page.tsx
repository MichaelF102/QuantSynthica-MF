import { PageHeader } from "@/components/ui/ui";
import { AssistantChat } from "@/components/AssistantChat";

export default function AssistantPage() {
  return (
    <>
      <PageHeader title="AI Research" accent="Assistant" subtitle="INTELLIGENCE" description="Ask about a fund's returns, risk or score, or how AMCs compare. Answers are built from the platform's calculations, with sources and dates." />
      <AssistantChat />
    </>
  );
}
