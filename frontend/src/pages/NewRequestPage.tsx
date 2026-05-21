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

export function NewRequestPage() {
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const { data: departments } = useAsync(() => api.departments(), []);

  const [form, setForm] = useState({
    department_id: "",
    subject: "",
    description: "",
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

            <div className="rounded-lg border border-accent-100 bg-accent-50 px-4 py-3 text-xs leading-relaxed text-accent-800">
              By submitting, you acknowledge that this request will be reviewed
              by the ministry's Information Officer. The response will be
              published to your dashboard once approved.
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
