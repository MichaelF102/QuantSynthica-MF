import { PageHeader } from "@/components/ui/ui";
import { AccountPanel } from "@/components/AccountPanel";

export default function AccountPage() {
  return (
    <>
      <PageHeader title="Your" accent="Account" subtitle="ACCOUNT" description="Sign in to keep watchlists and portfolios on the server." />
      <AccountPanel />
    </>
  );
}
