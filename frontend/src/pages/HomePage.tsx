import { Link } from "react-router-dom";
import { api } from "@/api/client";
import { Container, LinkButton, Spinner, ErrorBanner, Card } from "@/components/ui";
import { useAsync } from "@/lib/useAsync";
import { formatDate } from "@/lib/format";
import type { PublicFeedItem, Stats } from "@/types/api";

interface StatTile {
  label: string;
  value: number | string;
  hint?: string;
}

function StatGrid({ stats }: { stats: Stats }) {
  const tiles: StatTile[] = [
    { label: "Total requests", value: stats.total_requests },
    { label: "Responded", value: stats.responded, hint: "Closed with an official reply" },
    { label: "Under review", value: stats.under_review, hint: "Awaiting officer approval" },
    { label: "Pending", value: stats.pending, hint: "Newly filed" },
  ];
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {tiles.map((t) => (
        <Card key={t.label} className="px-5 py-4">
          <div className="label">{t.label}</div>
          <div className="mt-2 text-3xl font-semibold tracking-tight text-ink-900">
            {t.value}
          </div>
          {t.hint ? (
            <div className="mt-1 text-xs text-ink-500">{t.hint}</div>
          ) : null}
        </Card>
      ))}
    </div>
  );
}

function HeroFeaturedRequest({ req }: { req: PublicFeedItem }) {
  // Trim the response for the hero card so the layout stays compact.
  const snippet =
    req.response.length > 220 ? req.response.slice(0, 220).trimEnd() + "…" : req.response;
  return (
    <div className="rounded-2xl border border-ink-200 bg-ink-50 p-6 shadow-card">
      <div className="flex items-center justify-between border-b border-ink-200 pb-3">
        <div>
          <div className="text-xs text-ink-500">Latest public response</div>
          <div className="font-mono text-sm font-semibold text-ink-900">{req.id}</div>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          Responded
        </span>
      </div>
      <div className="mt-4 space-y-3">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-ink-500">
            Subject
          </div>
          <div className="mt-0.5 text-sm font-medium text-ink-900">{req.subject}</div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wider text-ink-500">
            Published
          </div>
          <div className="mt-0.5 text-sm text-ink-700">
            {formatDate(req.date_updated)}
          </div>
        </div>
        <div className="rounded-lg border border-ink-200 bg-white px-4 py-3">
          <div className="text-[11px] uppercase tracking-wider text-ink-500">
            Officer response
          </div>
          <p className="mt-1 whitespace-pre-wrap text-xs leading-relaxed text-ink-700">
            {snippet}
          </p>
        </div>
      </div>
    </div>
  );
}

function HeroPlaceholder() {
  return (
    <div className="rounded-2xl border border-dashed border-ink-200 bg-ink-50 p-6 text-center text-xs text-ink-500">
      No public responses yet — be the first to file a request.
    </div>
  );
}

export function HomePage() {
  const { data: stats, loading: statsLoading, error: statsError } =
    useAsync(() => api.stats(), []);
  const { data: feed, loading: feedLoading } = useAsync(() => api.publicFeed(5), []);
  const featured = feed && feed.length > 0 ? feed[0] : null;
  const rest = feed && feed.length > 1 ? feed.slice(1) : [];

  return (
    <>
      {/* Hero */}
      <section className="border-b border-ink-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="grid items-center gap-12 md:grid-cols-[1.2fr_1fr]">
            <div>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-ink-200 bg-ink-50 px-3 py-1 text-xs text-ink-600">
                <span className="h-1.5 w-1.5 rounded-full bg-accent-500" />
                Maldives RTI Portal · Act No. 1/2014
              </div>
              <h1 className="text-4xl font-semibold tracking-tight text-ink-900 sm:text-5xl">
                The right to know,
                <br />
                <span className="text-ink-500">delivered transparently.</span>
              </h1>
              <p className="mt-5 max-w-xl text-base leading-relaxed text-ink-600">
                File Right to Information requests with the Ministry of Climate
                Change, Environment and Energy. Responses are grounded in the
                ministry archive and reviewed by an Information Officer before
                publication.
              </p>
              <div className="mt-7 flex items-center gap-3">
                <LinkButton to="/requests/new" variant="primary" size="md">
                  File a request
                </LinkButton>
                <LinkButton to="/faqs" variant="ghost" size="md">
                  Read the FAQ
                </LinkButton>
              </div>
            </div>

            {/* Featured live public response (anonymised) */}
            <div className="relative hidden md:block">
              {feedLoading ? (
                <div className="h-64 animate-pulse rounded-2xl border border-ink-200 bg-ink-50" />
              ) : featured ? (
                <HeroFeaturedRequest req={featured} />
              ) : (
                <HeroPlaceholder />
              )}
            </div>
          </div>
        </div>
      </section>

      <Container>
        <h2 className="mb-5 text-sm font-medium uppercase tracking-[0.1em] text-ink-500">
          Platform overview
        </h2>
        {statsLoading ? <Spinner /> : null}
        {statsError ? (
          <ErrorBanner message={`Could not load stats — ${statsError}`} />
        ) : null}
        {stats ? <StatGrid stats={stats} /> : null}

        {/* Public feed — only published responses to "public" requests appear here. */}
        <section className="mt-16">
          <div className="mb-5 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-sm font-medium uppercase tracking-[0.1em] text-ink-500">
                Recent public responses
              </h2>
              <p className="mt-1 text-xs text-ink-500">
                Only requests filed publicly are shown — anonymous requests are
                excluded by design.
              </p>
            </div>
          </div>
          {rest.length === 0 && !featured && !feedLoading ? (
            <Card className="px-6 py-10 text-center text-sm text-ink-500">
              No public responses yet.
            </Card>
          ) : null}
          {rest.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2">
              {rest.map((req) => (
                <Card key={req.id} className="flex flex-col gap-3 px-5 py-4">
                  <div className="flex items-center justify-between text-xs text-ink-500">
                    <span className="font-mono font-medium text-ink-700">
                      {req.id}
                    </span>
                    <span>{formatDate(req.date_updated)}</span>
                  </div>
                  <div className="text-sm font-medium text-ink-900">
                    {req.subject}
                  </div>
                  <div className="text-xs text-ink-500">{req.department}</div>
                  <p className="line-clamp-3 text-xs leading-relaxed text-ink-700">
                    {req.response}
                  </p>
                </Card>
              ))}
            </div>
          ) : null}
        </section>

        <section className="mt-16">
          <h2 className="mb-5 text-sm font-medium uppercase tracking-[0.1em] text-ink-500">
            How it works
          </h2>
          <div className="grid gap-4 md:grid-cols-4">
            {[
              {
                step: "01",
                title: "File a request",
                desc: "Submit your information request publicly or anonymously.",
              },
              {
                step: "02",
                title: "AI structures it",
                desc: "An assistant extracts key questions and drafts a grounded response from past records.",
              },
              {
                step: "03",
                title: "Officer reviews",
                desc: "An Information Officer approves, edits, rejects, or asks for clarification.",
              },
              {
                step: "04",
                title: "You get an answer",
                desc: "Public responses appear here; anonymous ones stay between you and the officer.",
              },
            ].map((s) => (
              <Card key={s.step} className="px-5 py-5">
                <div className="font-mono text-xs text-ink-400">{s.step}</div>
                <div className="mt-3 text-sm font-semibold text-ink-900">
                  {s.title}
                </div>
                <p className="mt-2 text-xs leading-relaxed text-ink-500">
                  {s.desc}
                </p>
              </Card>
            ))}
          </div>
        </section>

        <section className="mt-16 mb-6 text-center text-xs text-ink-500">
          <Link to="/requests/new" className="font-medium text-accent-700 hover:text-accent-800">
            Need to file your own request?
          </Link>
        </section>
      </Container>
    </>
  );
}
