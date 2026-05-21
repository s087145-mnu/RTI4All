import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
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
  Spinner,
  StatusBadge,
  Textarea,
} from "@/components/ui";
import { useAsync } from "@/lib/useAsync";
import { formatDate } from "@/lib/format";
import type { ClarificationRequest, PublicRequest } from "@/types/api";

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-ink-100 py-2.5 last:border-b-0">
      <span className="text-xs font-medium text-ink-500">{label}</span>
      <span className="text-right text-sm text-ink-900">{value || "—"}</span>
    </div>
  );
}

function ProcessedAnalysis({ data }: { data: PublicRequest["processed_data"] }) {
  if (!data) return null;
  const items: Array<[string, React.ReactNode]> = [
    ["Type", data.request_type],
    ["Complexity", data.estimated_complexity],
    [
      "Completeness",
      typeof data.completeness_score === "number"
        ? `${(data.completeness_score * 100).toFixed(0)}%`
        : "—",
    ],
    ["Time period", data.time_period ?? "—"],
    ["Geographic scope", data.geographic_scope ?? "—"],
  ];

  return (
    <Card className="mt-6">
      <CardHeader
        title="AI analysis"
        description="Extracted from your request to help the officer route and resolve it."
      />
      <CardBody>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1">
            {items.map(([k, v]) => (
              <MetaRow key={k} label={k} value={v} />
            ))}
          </div>
          <div className="space-y-3">
            {data.key_questions && data.key_questions.length > 0 ? (
              <div>
                <div className="label mb-1.5">Key questions</div>
                <ul className="space-y-1 text-sm text-ink-800">
                  {data.key_questions.map((q, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-ink-400" />
                      <span>{q}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {data.suggested_response_approach ? (
              <div>
                <div className="label mb-1.5">Suggested approach</div>
                <p className="text-sm leading-relaxed text-ink-700">
                  {data.suggested_response_approach}
                </p>
              </div>
            ) : null}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

function ClarificationCard({
  clarification,
  onSubmit,
  submitting,
  error,
}: {
  clarification: ClarificationRequest;
  onSubmit: (payload: {
    updated_description?: string;
    additional_information?: string;
    answers_to_questions: Record<string, string>;
  }) => void;
  submitting: boolean;
  error: string | null;
}) {
  const [updatedDescription, setUpdatedDescription] = useState("");
  const [additionalInfo, setAdditionalInfo] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const handle = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({
      updated_description: updatedDescription || undefined,
      additional_information: additionalInfo || undefined,
      answers_to_questions: answers,
    });
  };

  return (
    <Card className="mt-6 border-amber-200">
      <CardHeader
        title="Clarification requested"
        description={`The officer has asked for more detail before this request can proceed.`}
      />
      <CardBody className="space-y-5">
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {clarification.message}
        </div>

        {clarification.missing_fields && clarification.missing_fields.length > 0 ? (
          <div>
            <div className="label mb-1.5">Missing information</div>
            <ul className="space-y-1 text-sm text-ink-700">
              {clarification.missing_fields.map((f, i) => (
                <li key={i} className="flex gap-2">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-ink-400" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <form onSubmit={handle} className="space-y-4">
          {clarification.questions && clarification.questions.length > 0 ? (
            <div className="space-y-3">
              <div className="label">Officer's questions</div>
              {clarification.questions.map((q, i) => (
                <Field key={i} label={q}>
                  <Textarea
                    rows={2}
                    value={answers[q] ?? ""}
                    onChange={(e) =>
                      setAnswers((a) => ({ ...a, [q]: e.target.value }))
                    }
                  />
                </Field>
              ))}
            </div>
          ) : null}

          <Field label="Updated description" hint="Optional — overwrites the original.">
            <Textarea
              rows={4}
              value={updatedDescription}
              onChange={(e) => setUpdatedDescription(e.target.value)}
            />
          </Field>

          <Field label="Additional information" hint="Optional.">
            <Textarea
              rows={3}
              value={additionalInfo}
              onChange={(e) => setAdditionalInfo(e.target.value)}
            />
          </Field>

          {error ? <ErrorBanner message={error} /> : null}

          <div className="flex justify-end">
            <Button variant="primary" type="submit" loading={submitting}>
              Send response to officer
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

export function RequestDetailPage() {
  const { id = "" } = useParams<{ id: string }>();
  const { token, user } = useAuth();
  const { data: req, loading, error, reload } = useAsync(
    () => api.getRequest(token!, id),
    [token, id],
  );

  const [clarSubmitting, setClarSubmitting] = useState(false);
  const [clarError, setClarError] = useState<string | null>(null);

  const handleClarify = async (payload: {
    updated_description?: string;
    additional_information?: string;
    answers_to_questions: Record<string, string>;
  }) => {
    setClarSubmitting(true);
    setClarError(null);
    try {
      await api.citizenClarify(token!, id, payload);
      reload();
    } catch (err: unknown) {
      setClarError(err instanceof Error ? err.message : String(err));
    } finally {
      setClarSubmitting(false);
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

  const status = req.status.toLowerCase();

  return (
    <Container>
      <Link
        to="/requests"
        className="mb-3 inline-flex items-center gap-1.5 text-xs font-medium text-ink-500 transition-colors hover:text-ink-900"
      >
        ← Back to my requests
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

      <div className="mt-8 grid gap-6 md:grid-cols-[1fr_280px]">
        <div className="space-y-6">
          <Card>
            <CardHeader title="Request" />
            <CardBody>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-800">
                {req.description}
              </p>
            </CardBody>
          </Card>

          {/* Outcome panel — varies based on status */}
          {status === "rejected" ? (
            <Card className="border-red-200">
              <CardHeader title="Request rejected" />
              <CardBody>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-800">
                  {req.rejection_reason ??
                    "No reason was recorded for the rejection."}
                </p>
              </CardBody>
            </Card>
          ) : null}

          {status === "responded" && req.response ? (
            <Card className="border-emerald-200">
              <CardHeader
                title="Official response"
                description={`Reviewed and published by the ministry on ${formatDate(req.date_updated)}.`}
              />
              <CardBody>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-800">
                  {req.response}
                </p>
              </CardBody>
            </Card>
          ) : null}

          {status === "under review" && req.response ? (
            <Card className="border-violet-200">
              <CardHeader
                title="Draft response"
                description="Pending officer approval — this is not yet the official reply."
              />
              <CardBody>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
                  {req.response}
                </p>
              </CardBody>
            </Card>
          ) : null}

          {status === "clarification needed" && req.clarification_requested ? (
            <ClarificationCard
              clarification={req.clarification_requested}
              onSubmit={handleClarify}
              submitting={clarSubmitting}
              error={clarError}
            />
          ) : null}

          {!req.response &&
          status !== "rejected" &&
          status !== "clarification needed" ? (
            <Card className="border-amber-200 bg-amber-50/40">
              <CardBody>
                <p className="text-sm text-amber-900">
                  No response yet. Public authorities have 30 days to reply to
                  RTI requests under the Act.
                </p>
              </CardBody>
            </Card>
          ) : null}

          <ProcessedAnalysis data={req.processed_data} />
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader title="Details" />
            <CardBody className="py-2">
              <MetaRow label="Status" value={<StatusBadge status={req.status} />} />
              <MetaRow label="Filed" value={formatDate(req.date_filed)} />
              <MetaRow label="Last updated" value={formatDate(req.date_updated)} />
              <MetaRow label="Department" value={req.department} />
              <MetaRow label="Citizen" value={req.citizen_name} />
              {user?.is_admin ? (
                <MetaRow label="Email" value={req.email} />
              ) : null}
            </CardBody>
          </Card>

          {req.clarification_history && req.clarification_history.length > 0 ? (
            <Card>
              <CardHeader title="History" />
              <CardBody className="space-y-3 py-3">
                {req.clarification_history.map((h, i) => (
                  <div key={i} className="border-l-2 border-ink-200 pl-3">
                    <div className="text-[11px] uppercase tracking-wider text-ink-500">
                      {formatDate(h.timestamp)}
                    </div>
                    <div className="text-xs text-ink-700">
                      Clarification requested by{" "}
                      <span className="font-medium">{h.requested_by}</span>
                    </div>
                  </div>
                ))}
              </CardBody>
            </Card>
          ) : null}
        </aside>
      </div>
    </Container>
  );
}
