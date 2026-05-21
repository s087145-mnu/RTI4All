import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import {
  Card,
  Container,
  EmptyState,
  ErrorBanner,
  Input,
  LinkButton,
  PageHeader,
  Select,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { useAsync } from "@/lib/useAsync";
import { formatDate, normaliseTerm } from "@/lib/format";

const STATUS_OPTIONS = [
  "all",
  "pending",
  "in progress",
  "under review",
  "clarification needed",
  "responded",
  "rejected",
] as const;

export function RequestsPage() {
  const { token, user } = useAuth();
  const { data, loading, error } = useAsync(
    () => api.listMyRequests(token!),
    [token],
  );

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.filter((r) => {
      const matchStatus =
        statusFilter === "all" || normaliseTerm(r.status) === statusFilter;
      const q = normaliseTerm(search);
      const matchSearch =
        !q ||
        r.subject.toLowerCase().includes(q) ||
        r.department.toLowerCase().includes(q) ||
        r.id.toLowerCase().includes(q);
      return matchStatus && matchSearch;
    });
  }, [data, statusFilter, search]);

  return (
    <Container>
      <PageHeader
        title="Requests"
        description={
          user?.is_admin
            ? "All requests on the platform (admin view)."
            : "Track requests you've filed under the RTI Act."
        }
        actions={
          <LinkButton to="/requests/new" variant="primary">
            New request
          </LinkButton>
        }
      />

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 px-5 py-3">
          <Input
            placeholder="Search by id, subject or department…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-sm"
          />
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="max-w-[180px]"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s === "all"
                  ? "All statuses"
                  : s.replace(/^./, (c) => c.toUpperCase())}
              </option>
            ))}
          </Select>
          {data ? (
            <span className="ml-auto text-xs text-ink-500">
              {filtered.length} of {data.length}
            </span>
          ) : null}
        </div>

        {loading ? <Spinner /> : null}
        {error ? (
          <div className="p-5">
            <ErrorBanner message={`Failed to load requests — ${error}`} />
          </div>
        ) : null}

        {data && filtered.length === 0 && !loading ? (
          <EmptyState
            title="No requests match your filters"
            description="Try clearing the search or selecting a different status."
          />
        ) : null}

        {data && filtered.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ink-100 bg-ink-50/60">
                  {["ID", "Subject", "Department", "Status", "Filed"].map(
                    (h) => (
                      <th key={h} className="label px-5 py-2.5 text-left">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {filtered.map((req) => (
                  <tr
                    key={req.id}
                    className="border-b border-ink-100 last:border-b-0 hover:bg-ink-50/60"
                  >
                    <td className="px-5 py-3">
                      <Link
                        to={`/requests/${req.id}`}
                        className="font-mono text-xs font-medium text-ink-900 hover:text-accent-700"
                      >
                        {req.id}
                      </Link>
                    </td>
                    <td className="max-w-md truncate px-5 py-3">
                      <Link
                        to={`/requests/${req.id}`}
                        className="text-ink-800 hover:text-ink-950"
                      >
                        {req.subject}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-ink-600">{req.department}</td>
                    <td className="px-5 py-3">
                      <StatusBadge status={req.status} />
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-xs text-ink-500">
                      {formatDate(req.date_filed)}
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
