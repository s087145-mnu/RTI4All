import { api } from "@/api/client";
import {
  Card,
  Container,
  EmptyState,
  ErrorBanner,
  LinkButton,
  PageHeader,
  Spinner,
} from "@/components/ui";
import { useAsync } from "@/lib/useAsync";

export function DepartmentsPage() {
  const { data, loading, error } = useAsync(() => api.departments(), []);

  return (
    <Container>
      <PageHeader
        title="Departments"
        description="Public authorities you can address requests to."
      />

      {loading ? <Spinner /> : null}
      {error ? <ErrorBanner message={`Could not load — ${error}`} /> : null}

      {data && data.length === 0 ? (
        <EmptyState
          title="No departments configured"
          description="Reach out to the portal administrator."
        />
      ) : null}

      {data && data.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((d) => (
            <Card key={d.id} className="flex flex-col px-6 py-5">
              <div className="font-mono text-[11px] uppercase tracking-wider text-ink-400">
                {d.id}
              </div>
              <h2 className="mt-2 text-base font-semibold text-ink-900">
                {d.name}
              </h2>
              {d.description ? (
                <p className="mt-2 text-sm leading-relaxed text-ink-600">
                  {d.description}
                </p>
              ) : null}
              <div className="mt-4 flex items-center justify-between border-t border-ink-100 pt-3">
                <a
                  href={`mailto:${d.contact_email}`}
                  className="text-xs text-ink-500 transition-colors hover:text-accent-700"
                >
                  {d.contact_email}
                </a>
                <LinkButton to="/requests/new" size="sm" variant="secondary">
                  File request
                </LinkButton>
              </div>
            </Card>
          ))}
        </div>
      ) : null}
    </Container>
  );
}
