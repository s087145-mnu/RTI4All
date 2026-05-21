import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
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
  Spinner,
  StatusBadge,
  Textarea,
} from "@/components/ui";
import { useAsync } from "@/lib/useAsync";
import { formatDate } from "@/lib/format";
import type { AdminUpdatePayload } from "@/types/api";

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-ink-100 py-2.5 last:border-b-0">
      <span className="text-xs font-medium text-ink-500">{label}</span>
      <span className="text-right text-sm text-ink-900">{value || "—"}</span>
    </div>
  );
}

type SaveAction = "approve" | "reject" | "save" | "clarify" | null;

export function AdminReviewPage() {
  const { id = "" } = useParams<{ id: string }>();
  const { token } = useAuth();
  const navigate = useNavigate();
  const { data: req, loading, error, reload } = useAsync(
    () => api.adminGetRequest(token!, id),
    [token, id],
  );

  const [draft, setDraft] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");

  const [clarMessage, setClarMessage] = useState("");
  const [clarQuestions, setClarQuestions] = useState("");
  const [clarMissingFields, setClarMissingFields] = useState("");

  const [action, setAction] = useState<SaveAction>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (req) {
      setDraft(req.response ?? "");
      setRejectionReason(req.rejection_reason ?? "");
    }
  }, [req]);

  const patch = async (payload: AdminUpdatePayload) =>
    api.adminUpdateRequest(token!, id, payload);

  const handle = async (kind: Exclude<SaveAction, null>) => {
    setAction(kind);
    setActionError(null);
    try {
      if (kind === "approve") {
        await patch({ response: draft, status: "Responded" });
        navigate("/admin");
        return;
      }
      if (kind === "reject") {
        if (!rejectionReason.trim()) {
          throw new Error("Please provide a rejection reason.");
        }
        await patch({ status: "Rejected", rejection_reason: rejectionReason });
        navigate("/admin");
        return;
      }
      if (kind === "save") {
        await patch({ response: draft });
        await reload();
        return;
      }
      if (kind === "clarify") {
        if (!clarMessage.trim()) {
          throw new Error("Please add a message for the citizen.");
        }
        await patch({
          request_clarification: {
            message: clarMessage,
            questions: clarQuestions
              .split("\n")
              .map((s) => s.trim())
              .filter(Boolean),
            missing_fields: clarMissingFields
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean),
          },
        });
        navigate("/admin");
        return;
      }
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setAction(null);
    }
  };

  if (loading) {
    return (
      <Container>
        <Spinner />
      </Container>
    );
  }
  if (error || !req) {
    return (
      <Container>
        <ErrorBanner message={error ?? "Request not found."} />
      </Container>
    );
  }

  return (
    <Container>
      <Link
        to="/admin"
        className="mb-3 inline-flex items-center gap-1.5 text-xs font-medium text-ink-500 transition-colors hover:text-ink-900"
      >
        ← Back to inbox
      </Link>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="font-mono text-xs text-ink-500">{req.id}</div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink-900">
            {req.subject}
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            {req.department} · filed {formatDate(req.date_filed)}
          </p>
        </div>
        <StatusBadge status={req.status} size="md" />
      </div>

      <div className="mt-8 grid gap-6 md:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <Card>
            <CardHeader title="Citizen's request" />
            <CardBody>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-800">
                {req.description}
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Response draft"
              description="Edit then approve to publish. The text below is what the citizen will see."
            />
            <CardBody>
              <Textarea
                rows={10}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Draft a response to the citizen…"
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Reject"
              description="Provide a clear reason; the citizen will see this verbatim."
            />
            <CardBody>
              <Field label="Rejection reason">
                <Textarea
                  rows={3}
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="e.g. Exempt under section 8(1)(j) of the RTI Act."
                />
              </Field>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Request clarification"
              description="Ask the citizen for more detail before responding."
            />
            <CardBody className="space-y-4">
              <Field label="Message to citizen" required>
                <Textarea
                  rows={3}
                  value={clarMessage}
                  onChange={(e) => setClarMessage(e.target.value)}
                  placeholder="What do you need clarified?"
                />
              </Field>
              <Field label="Specific questions" hint="One per line.">
                <Textarea
                  rows={3}
                  value={clarQuestions}
                  onChange={(e) => setClarQuestions(e.target.value)}
                  placeholder={"Which atoll?\nWhich quarter?"}
                />
              </Field>
              <Field label="Missing fields" hint="Comma-separated.">
                <Input
                  value={clarMissingFields}
                  onChange={(e) => setClarMissingFields(e.target.value)}
                  placeholder="geographic_scope, time_period"
                />
              </Field>
            </CardBody>
          </Card>

          {actionError ? <ErrorBanner message={actionError} /> : null}

          <div className="sticky bottom-4 z-20 flex flex-wrap items-center justify-end gap-2 rounded-xl border border-ink-200 bg-white/95 px-4 py-3 shadow-card backdrop-blur">
            <Button
              variant="ghost"
              onClick={() => handle("save")}
              loading={action === "save"}
              disabled={action !== null}
            >
              Save draft
            </Button>
            <Button
              variant="secondary"
              onClick={() => handle("clarify")}
              loading={action === "clarify"}
              disabled={action !== null}
            >
              Ask for clarification
            </Button>
            <Button
              variant="danger"
              onClick={() => handle("reject")}
              loading={action === "reject"}
              disabled={action !== null}
            >
              Reject
            </Button>
            <Button
              variant="primary"
              onClick={() => handle("approve")}
              loading={action === "approve"}
              disabled={action !== null}
            >
              Approve & publish
            </Button>
          </div>
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader title="Citizen" />
            <CardBody className="py-2">
              <MetaRow label="Name" value={req.citizen_name} />
              <MetaRow label="Email" value={req.email} />
              <MetaRow label="Phone" value={req.citizen_phone} />
              <MetaRow label="Address" value={req.citizen_address} />
              <MetaRow label="ID card" value={req.citizen_id_card} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Audit" />
            <CardBody className="py-2">
              <MetaRow label="Status" value={<StatusBadge status={req.status} />} />
              <MetaRow label="Filed" value={formatDate(req.date_filed)} />
              <MetaRow label="Last updated" value={formatDate(req.date_updated)} />
              <MetaRow label="Reviewed by" value={req.reviewed_by} />
              <MetaRow label="Reviewed at" value={formatDate(req.reviewed_at)} />
            </CardBody>
          </Card>

          {req.processed_data ? (
            <Card>
              <CardHeader title="AI analysis" />
              <CardBody className="py-2">
                <MetaRow label="Type" value={req.processed_data.request_type} />
                <MetaRow
                  label="Complexity"
                  value={req.processed_data.estimated_complexity}
                />
                <MetaRow
                  label="Completeness"
                  value={
                    typeof req.processed_data.completeness_score === "number"
                      ? `${(req.processed_data.completeness_score * 100).toFixed(0)}%`
                      : "—"
                  }
                />
              </CardBody>
            </Card>
          ) : null}
        </aside>
      </div>
    </Container>
  );
}
