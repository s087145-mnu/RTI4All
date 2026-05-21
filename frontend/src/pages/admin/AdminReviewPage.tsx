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
  const {
    data: req,
    loading,
    error,
    reload,
  } = useAsync(() => api.adminGetRequest(token!, id), [token, id]);

  const [draft, setDraft] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");

  const [clarMessage, setClarMessage] = useState("");
  const [clarQuestions, setClarQuestions] = useState("");
  const [clarMissingFields, setClarMissingFields] = useState("");

  const [action, setAction] = useState<SaveAction>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Track unsaved changes
  useEffect(() => {
    if (req) {
      const draftChanged = draft !== (req.response ?? "");
      const rejectionChanged = rejectionReason !== (req.rejection_reason ?? "");
      setHasUnsavedChanges(draftChanged || rejectionChanged);
    }
  }, [draft, rejectionReason, req]);

  // Warn before leaving with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + S to save draft
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (action === null) {
          handle("save");
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [action, draft]); // eslint-disable-line react-hooks/exhaustive-deps

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
    setActionSuccess(null);

    // Confirm destructive actions
    if (kind === "approve") {
      const confirmed = window.confirm(
        "Are you sure you want to approve and publish this response? The citizen will be able to see it immediately.",
      );
      if (!confirmed) {
        setAction(null);
        return;
      }
    }

    if (kind === "reject") {
      const confirmed = window.confirm(
        "Are you sure you want to reject this request? This action will notify the citizen.",
      );
      if (!confirmed) {
        setAction(null);
        return;
      }
    }

    try {
      if (kind === "approve") {
        const trimmedDraft = draft.trim();
        if (!trimmedDraft) {
          throw new Error("Please provide a response before approving.");
        }
        await patch({ response: trimmedDraft, status: "Responded" });
        navigate("/admin");
        return;
      }
      if (kind === "reject") {
        const trimmedReason = rejectionReason.trim();
        if (!trimmedReason) {
          throw new Error("Please provide a rejection reason.");
        }
        await patch({ status: "Rejected", rejection_reason: trimmedReason });
        navigate("/admin");
        return;
      }
      if (kind === "save") {
        const trimmedDraft = draft.trim();
        if (!trimmedDraft) {
          throw new Error("Cannot save an empty draft.");
        }
        await patch({ response: trimmedDraft });
        await reload();
        setActionSuccess("✓ Draft saved successfully");
        setTimeout(() => setActionSuccess(null), 3000);
        return;
      }
      if (kind === "clarify") {
        const trimmedMessage = clarMessage.trim();
        if (!trimmedMessage) {
          throw new Error("Please add a message for the citizen.");
        }
        const questions = clarQuestions
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean);
        const missingFields = clarMissingFields
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);

        await patch({
          request_clarification: {
            message: trimmedMessage,
            questions,
            missing_fields: missingFields,
          },
        });
        navigate("/admin");
        return;
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setActionError(err.message);
      } else {
        setActionError(String(err));
      }
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
        onClick={(e) => {
          if (hasUnsavedChanges) {
            const confirmed = window.confirm(
              "You have unsaved changes. Are you sure you want to leave?",
            );
            if (!confirmed) {
              e.preventDefault();
            }
          }
        }}
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
          {actionSuccess ? (
            <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
              {actionSuccess}
            </div>
          ) : null}

          <div className="sticky bottom-4 z-20 flex flex-wrap items-center justify-end gap-2 rounded-xl border border-ink-200 bg-white/95 px-4 py-3 shadow-card backdrop-blur">
            <Button
              variant="ghost"
              onClick={() => handle("save")}
              loading={action === "save"}
              disabled={action !== null || !hasUnsavedChanges}
            >
              {hasUnsavedChanges ? "Save draft *" : "Save draft"}
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
              <MetaRow
                label="Status"
                value={<StatusBadge status={req.status} />}
              />
              <MetaRow label="Filed" value={formatDate(req.date_filed)} />
              <MetaRow
                label="Last updated"
                value={formatDate(req.date_updated)}
              />
              <MetaRow label="Reviewed by" value={req.reviewed_by} />
              <MetaRow
                label="Reviewed at"
                value={formatDate(req.reviewed_at)}
              />
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
