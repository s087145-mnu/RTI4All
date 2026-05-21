/** Render an ISO date string as e.g. "12 Feb 2024", or em-dash on bad input. */
export function formatDate(iso: string | undefined | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** Lowercase + trim helper used by client-side filtering. */
export function normaliseTerm(s: string): string {
  return s.toLowerCase().trim();
}
