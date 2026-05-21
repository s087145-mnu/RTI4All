import { useState } from "react";
import { api } from "@/api/client";
import {
  Container,
  EmptyState,
  ErrorBanner,
  PageHeader,
  Spinner,
} from "@/components/ui";
import { useAsync } from "@/lib/useAsync";
import { cn } from "@/lib/cn";

export function FaqsPage() {
  const { data, loading, error } = useAsync(() => api.faqs(), []);
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <Container size="md">
      <PageHeader
        title="Frequently asked questions"
        description="Common questions about the RTI process in the Maldives."
      />

      {loading ? <Spinner /> : null}
      {error ? <ErrorBanner message={`Could not load — ${error}`} /> : null}

      {data && data.length === 0 ? (
        <EmptyState title="No FAQs available yet" />
      ) : null}

      {data && data.length > 0 ? (
        <div className="divide-y divide-ink-200 rounded-xl border border-ink-200 bg-white">
          {data.map((faq) => {
            const open = openId === faq.id;
            return (
              <details
                key={faq.id}
                className="group"
                open={open}
                onToggle={(e) => {
                  const el = e.currentTarget as HTMLDetailsElement;
                  setOpenId(el.open ? faq.id : null);
                }}
              >
                <summary
                  className={cn(
                    "flex cursor-pointer items-center justify-between gap-4 px-5 py-4 text-sm font-medium text-ink-900 transition-colors hover:bg-ink-50",
                  )}
                >
                  <span>{faq.question}</span>
                  <span
                    className={cn(
                      "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-ink-200 text-xs text-ink-500 transition-transform",
                      open && "rotate-45 border-accent-300 text-accent-700",
                    )}
                  >
                    +
                  </span>
                </summary>
                <div className="border-t border-ink-100 bg-ink-50/40 px-5 py-4 text-sm leading-relaxed text-ink-700">
                  {faq.answer}
                </div>
              </details>
            );
          })}
        </div>
      ) : null}
    </Container>
  );
}
