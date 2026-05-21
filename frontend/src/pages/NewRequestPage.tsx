import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Container,
  ErrorBanner,
  Field,
  Input,
  LinkButton,
  PageHeader,
  Select,
  Textarea,
} from "@/components/ui";
import { useAsync } from "@/lib/useAsync";
import { cn } from "@/lib/cn";
import type { Visibility } from "@/types/api";

export function NewRequestPage() {
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const { data: departments } = useAsync(() => api.departments(), []);

  const [form, setForm] = useState({
    department_id: "",
    subject: "",
    description: "",
    visibility: "public" as Visibility,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Single-ministry portal: auto-fill if only one department is configured.
  const onlyDepartment =
    departments && departments.length === 1 ? departments[0] : null;
  useEffect(() => {
    if (onlyDepartment && !form.department_id) {
      setForm((f) => ({ ...f, department_id: onlyDepartment.id }));
    }
  }, [onlyDepartment, form.department_id]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.createRequest(token!, form);
      navigate(`/requests/${created.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  return (
    <Container size="md">
      <PageHeader
        title="File an RTI request"
        description="Submit a Right to Information request. A response is expected within 30 days under the RTI Act."
      />

      {error ? (
        <div className="mb-4">
          <ErrorBanner message={`Submission failed — ${error}`} />
        </div>
      ) : null}

      <Card>
        <CardHeader
          title="Request details"
          description="Be specific so the officer can locate the records you need."
        />
        <CardBody>
          <div className="mb-5 rounded-lg border border-ink-200 bg-ink-50/60 px-4 py-3">
            <div className="text-[11px] uppercase tracking-wider text-ink-500">
              Filing as
            </div>
            <div className="mt-0.5 text-sm font-medium text-ink-900">
              {user?.full_name}{" "}
              <span className="text-ink-500 font-normal">· {user?.email}</span>
            </div>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            <Field label="Department" required>
              {onlyDepartment ? (
                <div className="flex h-10 items-center rounded-lg border border-ink-200 bg-ink-50/40 px-3.5 text-sm text-ink-700">
                  {onlyDepartment.name}
                </div>
              ) : (
                <Select
                  required
                  value={form.department_id}
                  onChange={(e) =>
                    setForm({ ...form, department_id: e.target.value })
                  }
                >
                  <option value="">— Select a department —</option>
                  {(departments ?? []).map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>

            <Field label="Subject" required>
              <Input
                required
                placeholder="A brief summary, e.g. Coral reef monitoring 2024"
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
              />
            </Field>

            <Field
              label="Description"
              required
              hint="Include the time period, geography, and specific documents you need."
            >
              <Textarea
                required
                rows={7}
                placeholder="Please provide the …"
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
              />
            </Field>

            {/* Visibility selector — two big radio cards.
              * Public requests appear on the public homepage feed once
              * responded; anonymous requests never do. Both are reviewed by
              * the same officer the same way. */}
            <div>
              <span className="mb-1.5 block text-xs font-medium text-ink-700">
                Visibility <span className="ml-0.5 text-accent-600">*</span>
              </span>
              <div className="grid gap-3 sm:grid-cols-2">
                {(
                  [
                    {
                      key: "public" as Visibility,
                      title: "Public",
                      desc: "Once responded, this question and the official reply may appear on the homepage feed.",
                      icon: "🌐",
                    },
                    {
                      key: "anonymous" as Visibility,
                      title: "Anonymous",
                      desc: "Only you and the reviewing officer ever see this request. It will not appear publicly.",
                      icon: "🔒",
                    },
                  ] as const
                ).map((opt) => {
                  const active = form.visibility === opt.key;
                  return (
                    <button
                      key={opt.key}
                      type="button"
                      onClick={() =>
                        setForm({ ...form, visibility: opt.key })
                      }
                      className={cn(
                        "rounded-lg border px-4 py-3 text-left transition-colors",
                        active
                          ? "border-accent-500 bg-accent-50/60 ring-1 ring-accent-200"
                          : "border-ink-200 bg-white hover:border-ink-300 hover:bg-ink-50",
                      )}
                    >
                      <div className="flex items-center gap-2 text-sm font-medium text-ink-900">
                        <span aria-hidden>{opt.icon}</span>
                        {opt.title}
                        {active ? (
                          <span className="ml-auto text-[10px] uppercase tracking-wider text-accent-700">
                            Selected
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-ink-500">
                        {opt.desc}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="rounded-lg border border-accent-100 bg-accent-50 px-4 py-3 text-xs leading-relaxed text-accent-800">
              By submitting, you acknowledge that this request will be reviewed
              by the ministry's Information Officer. The response will be
              published to your dashboard once approved.
              {form.visibility === "anonymous" ? (
                <>
                  {" "}You've chosen <span className="font-semibold">Anonymous</span>{" "}
                  — your name and email are still shared with the reviewing
                  officer, but the request will never appear on the public feed.
                </>
              ) : null}
            </div>

            <div className="flex items-center justify-end gap-3">
              <LinkButton to="/requests" variant="ghost">
                Cancel
              </LinkButton>
              <Button type="submit" variant="primary" loading={submitting}>
                {submitting ? "Submitting…" : "Submit request"}
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </Container>
  );
}
