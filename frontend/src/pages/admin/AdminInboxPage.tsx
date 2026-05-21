import { Link } from "react-router-dom";
import { useEffect } from "react";
import { api } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import {
  Card,
  Container,
  EmptyState,
  ErrorBanner,
  LinkButton,
  PageHeader,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { useAsync } from "@/lib/useAsync";
import { formatDate } from "@/lib/format";

export function AdminInboxPage() {
  const { token } = useAuth();
  const { data, loading, error, reload } = useAsync(
    () => api.adminPending(token!),
    [token],
  );

  // Auto-reload every 30 seconds to keep inbox fresh
  useEffect(() => {
    const interval = setInterval(() => {
      reload();
    }, 30000);
    return () => clearInterval(interval);
  }, [reload]);

  return (
    <Container>
      <PageHeader
        title="Review inbox"
        description="Requests awaiting officer review. Oldest first."
      />

      <Card className="overflow-hidden">
        {loading ? <Spinner /> : null}
        {error ? (
          <div className="p-5">
            <ErrorBanner message={`Failed to load inbox — ${error}`} />
          </div>
        ) : null}

        {data && data.length === 0 ? (
          <EmptyState
            title="Inbox is clear"
            description="All filed requests have been reviewed."
          />
        ) : null}

        {data && data.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ink-100 bg-ink-50/60">
                  {["ID", "Citizen", "Subject", "Status", "Filed", ""].map(
                    (h) => (
                      <th key={h} className="label px-5 py-2.5 text-left">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {data.map((req) => (
                  <tr
                    key={req.id}
                    className="border-b border-ink-100 last:border-b-0 hover:bg-ink-50/60"
                  >
                    <td className="px-5 py-3 font-mono text-xs font-medium text-ink-900">
                      {req.id}
                    </td>
                    <td className="px-5 py-3">
                      <div className="text-sm text-ink-900">
                        {req.citizen_name}
                      </div>
                      <div className="text-[11px] text-ink-500">
                        {req.email}
                      </div>
                    </td>
                    <td className="max-w-md truncate px-5 py-3">
                      <Link
                        to={`/admin/requests/${req.id}`}
                        className="text-ink-800 hover:text-ink-950"
                      >
                        {req.subject}
                      </Link>
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={req.status} />
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-xs text-ink-500">
                      {formatDate(req.date_filed)}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <LinkButton
                        to={`/admin/requests/${req.id}`}
                        size="sm"
                        variant="primary"
                      >
                        Review
                      </LinkButton>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>
    </Container>
  );
}
