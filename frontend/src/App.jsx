import { useState, useEffect } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Link,
  NavLink,
  useNavigate,
  useParams,
} from "react-router-dom";

// ─── Design tokens ───────────────────────────────────────────────────────────
const PRIMARY = "#1a6eb5";
const BG = "#f5f7fa";
const CARD_BG = "#ffffff";
const BORDER = "#dde3ec";
const TEXT = "#1a1f2e";
const MUTED = "#6b7a99";
const SUCCESS = "#1a9e5f";
const WARNING = "#d97706";
const DANGER = "#dc2626";
const INFO = "#0891b2";

const STATUS_COLORS = {
  pending: { bg: "#fef3c7", color: "#92400e" },
  "in progress": { bg: "#dbeafe", color: "#1e40af" },
  responded: { bg: "#d1fae5", color: "#065f46" },
  rejected: { bg: "#fee2e2", color: "#991b1b" },
};

function statusChip(status = "") {
  const key = status.toLowerCase();
  const style = STATUS_COLORS[key] ?? { bg: "#f3f4f6", color: "#374151" };
  return {
    display: "inline-block",
    padding: "2px 10px",
    borderRadius: "999px",
    fontSize: "0.75rem",
    fontWeight: 600,
    letterSpacing: "0.03em",
    textTransform: "capitalize",
    ...style,
  };
}

// ─── Shared helpers ───────────────────────────────────────────────────────────
function useFetch(url) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!url) return;
    setLoading(true);
    setError(null);
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [url]);

  return { data, loading, error };
}

function Spinner() {
  return (
    <div
      style={{ display: "flex", justifyContent: "center", padding: "60px 0" }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          border: `4px solid ${BORDER}`,
          borderTopColor: PRIMARY,
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
        }}
      />
    </div>
  );
}

function ErrorBanner({ message }) {
  return (
    <div
      style={{
        background: "#fef2f2",
        border: `1px solid #fecaca`,
        borderRadius: 8,
        padding: "16px 20px",
        color: DANGER,
        margin: "24px 0",
        fontWeight: 500,
      }}
    >
      ⚠ {message}
    </div>
  );
}

function Card({ children, style = {} }) {
  return (
    <div
      style={{
        background: CARD_BG,
        border: `1px solid ${BORDER}`,
        borderRadius: 12,
        padding: "24px",
        boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function PageWrapper({ children }) {
  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
      {children}
    </main>
  );
}

function PageTitle({ children }) {
  return (
    <h1
      style={{
        fontSize: "1.75rem",
        fontWeight: 700,
        color: TEXT,
        marginBottom: 8,
      }}
    >
      {children}
    </h1>
  );
}

function Subtitle({ children }) {
  return (
    <p style={{ color: MUTED, marginBottom: 28, fontSize: "1rem" }}>
      {children}
    </p>
  );
}

// ─── Navbar ───────────────────────────────────────────────────────────────────
function Navbar() {
  const linkStyle = (isActive) => ({
    color: isActive ? PRIMARY : TEXT,
    textDecoration: "none",
    fontWeight: isActive ? 600 : 500,
    fontSize: "0.9rem",
    padding: "6px 2px",
    borderBottom: isActive ? `2px solid ${PRIMARY}` : "2px solid transparent",
    transition: "color 0.15s, border-color 0.15s",
  });

  return (
    <nav
      style={{
        background: CARD_BG,
        borderBottom: `1px solid ${BORDER}`,
        position: "sticky",
        top: 0,
        zIndex: 100,
        boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
      }}
    >
      <div
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          padding: "0 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: 60,
        }}
      >
        {/* Logo / Brand */}
        <Link
          to="/"
          style={{
            textDecoration: "none",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <span
            style={{
              background: PRIMARY,
              color: "#fff",
              borderRadius: 8,
              padding: "4px 10px",
              fontWeight: 800,
              fontSize: "1rem",
              letterSpacing: "0.04em",
            }}
          >
            RTI4All
          </span>
          <span style={{ color: MUTED, fontSize: "0.8rem", fontWeight: 400 }}>
            Right to Information for All
          </span>
        </Link>

        {/* Nav links */}
        <div style={{ display: "flex", gap: 28, alignItems: "center" }}>
          {[
            { to: "/", label: "Home" },
            { to: "/requests", label: "Requests" },
            { to: "/requests/new", label: "File RTI" },
            { to: "/departments", label: "Departments" },
            { to: "/faqs", label: "FAQs" },
          ].map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              style={({ isActive }) => linkStyle(isActive)}
            >
              {label}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  );
}

// ─── HomePage ────────────────────────────────────────────────────────────────
function HomePage() {
  const { data: stats, loading, error } = useFetch("/api/stats");

  return (
    <>
      {/* Hero */}
      <section
        style={{
          background: `linear-gradient(135deg, ${PRIMARY} 0%, #0d4f8c 100%)`,
          color: "#fff",
          padding: "80px 24px",
          textAlign: "center",
        }}
      >
        <div style={{ maxWidth: 680, margin: "0 auto" }}>
          <div style={{ fontSize: "3rem", marginBottom: 16 }}>📋</div>
          <h1
            style={{
              fontSize: "2.8rem",
              fontWeight: 800,
              margin: "0 0 16px",
              lineHeight: 1.2,
            }}
          >
            Your Right to Know
          </h1>
          <p
            style={{
              fontSize: "1.15rem",
              opacity: 0.88,
              lineHeight: 1.7,
              marginBottom: 36,
            }}
          >
            File, track, and manage your Right to Information requests with
            ease. Transparency and accountability — for every citizen.
          </p>
          <Link
            to="/requests/new"
            style={{
              display: "inline-block",
              background: "#fff",
              color: PRIMARY,
              fontWeight: 700,
              fontSize: "1rem",
              padding: "14px 36px",
              borderRadius: 8,
              textDecoration: "none",
              boxShadow: "0 4px 14px rgba(0,0,0,0.2)",
              transition: "transform 0.15s",
            }}
          >
            File an RTI Request →
          </Link>
        </div>
      </section>

      {/* Stats strip */}
      <section style={{ background: BG, padding: "48px 24px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <h2
            style={{
              textAlign: "center",
              color: TEXT,
              fontSize: "1.25rem",
              fontWeight: 600,
              marginBottom: 32,
            }}
          >
            Platform Overview
          </h2>

          {loading && <Spinner />}
          {error && <ErrorBanner message={`Could not load stats: ${error}`} />}
          {stats && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: 20,
              }}
            >
              {[
                {
                  label: "Total Requests",
                  value: stats.total_requests,
                  icon: "📨",
                  color: PRIMARY,
                },
                {
                  label: "Responded",
                  value: stats.responded,
                  icon: "✅",
                  color: SUCCESS,
                },
                {
                  label: "Pending",
                  value: stats.pending,
                  icon: "⏳",
                  color: WARNING,
                },
                {
                  label: "In Progress",
                  value: stats.in_progress,
                  icon: "🔄",
                  color: INFO,
                },
              ].map(({ label, value, icon, color }) => (
                <Card key={label} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: "2rem", marginBottom: 8 }}>
                    {icon}
                  </div>
                  <div style={{ fontSize: "2.2rem", fontWeight: 800, color }}>
                    {value ?? "—"}
                  </div>
                  <div
                    style={{
                      color: MUTED,
                      fontSize: "0.875rem",
                      fontWeight: 500,
                      marginTop: 4,
                    }}
                  >
                    {label}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* How it works */}
      <section
        style={{
          background: CARD_BG,
          padding: "56px 24px",
          borderTop: `1px solid ${BORDER}`,
        }}
      >
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <h2
            style={{
              textAlign: "center",
              color: TEXT,
              fontSize: "1.35rem",
              fontWeight: 700,
              marginBottom: 36,
            }}
          >
            How it Works
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: 28,
            }}
          >
            {[
              {
                step: "1",
                title: "File a Request",
                desc: "Submit your RTI request with the relevant department and your query.",
                icon: "📝",
              },
              {
                step: "2",
                title: "Track Progress",
                desc: "Monitor the status of your request in real time from your dashboard.",
                icon: "🔍",
              },
              {
                step: "3",
                title: "Get a Response",
                desc: "Receive an official response from the public authority within 30 days.",
                icon: "📬",
              },
              {
                step: "4",
                title: "Stay Informed",
                desc: "Use the information to hold governments and institutions accountable.",
                icon: "🏛️",
              },
            ].map(({ step, title, desc, icon }) => (
              <div
                key={step}
                style={{ textAlign: "center", padding: "8px 12px" }}
              >
                <div
                  style={{
                    width: 56,
                    height: 56,
                    borderRadius: "50%",
                    background: `${PRIMARY}18`,
                    color: PRIMARY,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "1.6rem",
                    margin: "0 auto 14px",
                  }}
                >
                  {icon}
                </div>
                <div
                  style={{
                    fontWeight: 700,
                    fontSize: "1rem",
                    color: TEXT,
                    marginBottom: 8,
                  }}
                >
                  {title}
                </div>
                <div
                  style={{
                    color: MUTED,
                    fontSize: "0.875rem",
                    lineHeight: 1.6,
                  }}
                >
                  {desc}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}

// ─── RequestsPage ─────────────────────────────────────────────────────────────
function RequestsPage() {
  const { data: requests, loading, error } = useFetch("/api/requests");
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");

  const filtered = (requests ?? []).filter((r) => {
    const matchStatus =
      statusFilter === "all" || r.status?.toLowerCase() === statusFilter;
    const q = search.toLowerCase();
    const matchSearch =
      !q ||
      r.citizen_name?.toLowerCase().includes(q) ||
      r.subject?.toLowerCase().includes(q) ||
      r.department?.toLowerCase().includes(q);
    return matchStatus && matchSearch;
  });

  return (
    <PageWrapper>
      <PageTitle>RTI Requests</PageTitle>
      <Subtitle>
        Browse and track all filed Right to Information requests.
      </Subtitle>

      {/* Filters */}
      <div
        style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap" }}
      >
        <input
          type="text"
          placeholder="Search by name, subject or department…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={inputStyle({ width: 300 })}
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={inputStyle({ width: 180 })}
        >
          <option value="all">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="in progress">In Progress</option>
          <option value="responded">Responded</option>
          <option value="rejected">Rejected</option>
        </select>
        <Link to="/requests/new" style={btnStyle(PRIMARY)}>
          + New Request
        </Link>
      </div>

      {loading && <Spinner />}
      {error && <ErrorBanner message={`Failed to load requests: ${error}`} />}

      {!loading && !error && (
        <>
          <div style={{ color: MUTED, fontSize: "0.875rem", marginBottom: 12 }}>
            Showing {filtered.length} of {requests.length} requests
          </div>
          <Card style={{ padding: 0, overflow: "hidden" }}>
            {filtered.length === 0 ? (
              <div style={{ padding: 40, textAlign: "center", color: MUTED }}>
                No requests match your filters.
              </div>
            ) : (
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: "0.9rem",
                }}
              >
                <thead>
                  <tr
                    style={{
                      background: BG,
                      borderBottom: `2px solid ${BORDER}`,
                    }}
                  >
                    {[
                      "ID",
                      "Citizen",
                      "Department",
                      "Subject",
                      "Status",
                      "Date Filed",
                    ].map((h) => (
                      <th
                        key={h}
                        style={{
                          padding: "12px 16px",
                          textAlign: "left",
                          color: MUTED,
                          fontWeight: 600,
                          fontSize: "0.8rem",
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((req, idx) => (
                    <tr
                      key={req.id}
                      style={{
                        borderBottom: `1px solid ${BORDER}`,
                        background: idx % 2 === 0 ? CARD_BG : "#fafbfd",
                        transition: "background 0.1s",
                      }}
                    >
                      <td style={tdStyle}>
                        <Link
                          to={`/requests/${req.id}`}
                          style={{
                            color: PRIMARY,
                            fontWeight: 600,
                            textDecoration: "none",
                          }}
                        >
                          #{req.id}
                        </Link>
                      </td>
                      <td style={tdStyle}>{req.citizen_name}</td>
                      <td style={tdStyle}>{req.department}</td>
                      <td
                        style={{
                          ...tdStyle,
                          maxWidth: 260,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        <Link
                          to={`/requests/${req.id}`}
                          style={{ color: TEXT, textDecoration: "none" }}
                        >
                          {req.subject}
                        </Link>
                      </td>
                      <td style={tdStyle}>
                        <span style={statusChip(req.status)}>{req.status}</span>
                      </td>
                      <td
                        style={{
                          ...tdStyle,
                          color: MUTED,
                          whiteSpace: "nowrap",
                        }}
                      >
                        {req.date_filed
                          ? new Date(req.date_filed).toLocaleDateString(
                              "en-IN",
                              {
                                day: "2-digit",
                                month: "short",
                                year: "numeric",
                              },
                            )
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </>
      )}
    </PageWrapper>
  );
}

// ─── RequestDetailPage ────────────────────────────────────────────────────────
function RequestDetailPage() {
  const { id } = useParams();
  const { data: req, loading, error } = useFetch(`/api/requests/${id}`);

  return (
    <PageWrapper>
      <Link
        to="/requests"
        style={{
          color: MUTED,
          textDecoration: "none",
          fontSize: "0.875rem",
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          marginBottom: 20,
        }}
      >
        ← Back to Requests
      </Link>

      {loading && <Spinner />}
      {error && (
        <ErrorBanner message={`Could not load request #${id}: ${error}`} />
      )}

      {req && (
        <>
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: 16,
              flexWrap: "wrap",
              marginBottom: 28,
            }}
          >
            <div>
              <PageTitle>Request #{req.id}</PageTitle>
              <p style={{ color: MUTED, margin: 0 }}>{req.subject}</p>
            </div>
            <span
              style={{
                ...statusChip(req.status),
                fontSize: "0.875rem",
                padding: "6px 16px",
                alignSelf: "flex-start",
                marginTop: 8,
              }}
            >
              {req.status}
            </span>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
              gap: 20,
              marginBottom: 20,
            }}
          >
            <Card>
              <SectionHeading>Citizen Information</SectionHeading>
              <DetailRow label="Full Name" value={req.citizen_name} />
              <DetailRow label="Email" value={req.email} />
              <DetailRow
                label="Date Filed"
                value={
                  req.date_filed
                    ? new Date(req.date_filed).toLocaleDateString("en-IN", {
                        dateStyle: "long",
                      })
                    : "—"
                }
              />
            </Card>
            <Card>
              <SectionHeading>Request Details</SectionHeading>
              <DetailRow label="Department" value={req.department} />
              <DetailRow label="Subject" value={req.subject} />
              <DetailRow label="Status" value={req.status} />
            </Card>
          </div>

          <Card style={{ marginBottom: 20 }}>
            <SectionHeading>Description</SectionHeading>
            <p
              style={{
                color: TEXT,
                lineHeight: 1.75,
                margin: 0,
                whiteSpace: "pre-wrap",
              }}
            >
              {req.description || (
                <span style={{ color: MUTED }}>No description provided.</span>
              )}
            </p>
          </Card>

          {req.response && (
            <Card style={{ borderLeft: `4px solid ${SUCCESS}` }}>
              <SectionHeading style={{ color: SUCCESS }}>
                Official Response
              </SectionHeading>
              {req.response_date && (
                <p
                  style={{
                    color: MUTED,
                    fontSize: "0.85rem",
                    marginTop: -8,
                    marginBottom: 12,
                  }}
                >
                  Responded on{" "}
                  {new Date(req.response_date).toLocaleDateString("en-IN", {
                    dateStyle: "long",
                  })}
                </p>
              )}
              <p
                style={{
                  color: TEXT,
                  lineHeight: 1.75,
                  margin: 0,
                  whiteSpace: "pre-wrap",
                }}
              >
                {req.response}
              </p>
            </Card>
          )}

          {!req.response && (
            <Card
              style={{
                borderLeft: `4px solid ${WARNING}`,
                background: "#fffbeb",
              }}
            >
              <p style={{ margin: 0, color: "#92400e", fontWeight: 500 }}>
                ⏳ No response yet. Public authorities have 30 days to respond
                to RTI requests.
              </p>
            </Card>
          )}
        </>
      )}
    </PageWrapper>
  );
}

function SectionHeading({ children, style = {} }) {
  return (
    <h3
      style={{
        fontSize: "0.8rem",
        fontWeight: 700,
        color: MUTED,
        textTransform: "uppercase",
        letterSpacing: "0.07em",
        marginBottom: 16,
        ...style,
      }}
    >
      {children}
    </h3>
  );
}

function DetailRow({ label, value }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: 16,
        padding: "8px 0",
        borderBottom: `1px solid ${BORDER}`,
        fontSize: "0.9rem",
      }}
    >
      <span style={{ color: MUTED, fontWeight: 500, flexShrink: 0 }}>
        {label}
      </span>
      <span
        style={{ color: TEXT, textAlign: "right", wordBreak: "break-word" }}
      >
        {value || "—"}
      </span>
    </div>
  );
}

// ─── NewRequestPage ───────────────────────────────────────────────────────────
function NewRequestPage() {
  const navigate = useNavigate();
  const { data: departments } = useFetch("/api/departments");

  const [form, setForm] = useState({
    citizen_name: "",
    email: "",
    department_id: "",
    subject: "",
    description: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const handleChange = (e) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await fetch("/api/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          department_id: Number(form.department_id),
        }),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || `HTTP ${res.status}`);
      }
      const created = await res.json();
      navigate(`/requests/${created.id}`);
    } catch (err) {
      setSubmitError(err.message);
      setSubmitting(false);
    }
  };

  const fieldStyle = { display: "flex", flexDirection: "column", gap: 6 };
  const labelStyle = { fontSize: "0.875rem", fontWeight: 600, color: TEXT };

  return (
    <PageWrapper>
      <div style={{ maxWidth: 680, margin: "0 auto" }}>
        <PageTitle>File an RTI Request</PageTitle>
        <Subtitle>
          Submit a Right to Information request to any public authority. You
          will receive a response within 30 days as mandated by the RTI Act.
        </Subtitle>

        {submitError && (
          <ErrorBanner message={`Submission failed: ${submitError}`} />
        )}

        <Card>
          <form
            onSubmit={handleSubmit}
            style={{ display: "flex", flexDirection: "column", gap: 20 }}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 16,
              }}
            >
              <div style={fieldStyle}>
                <label style={labelStyle}>Full Name *</label>
                <input
                  name="citizen_name"
                  required
                  value={form.citizen_name}
                  onChange={handleChange}
                  placeholder="e.g. Priya Sharma"
                  style={inputStyle()}
                />
              </div>
              <div style={fieldStyle}>
                <label style={labelStyle}>Email Address *</label>
                <input
                  name="email"
                  type="email"
                  required
                  value={form.email}
                  onChange={handleChange}
                  placeholder="e.g. priya@email.com"
                  style={inputStyle()}
                />
              </div>
            </div>

            <div style={fieldStyle}>
              <label style={labelStyle}>Department *</label>
              <select
                name="department_id"
                required
                value={form.department_id}
                onChange={handleChange}
                style={inputStyle()}
              >
                <option value="">— Select a department —</option>
                {(departments ?? []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>

            <div style={fieldStyle}>
              <label style={labelStyle}>Subject *</label>
              <input
                name="subject"
                required
                value={form.subject}
                onChange={handleChange}
                placeholder="Brief subject of your RTI request"
                style={inputStyle()}
              />
            </div>

            <div style={fieldStyle}>
              <label style={labelStyle}>Description *</label>
              <textarea
                name="description"
                required
                value={form.description}
                onChange={handleChange}
                rows={6}
                placeholder="Describe the specific information you are seeking. Be as precise as possible to get an accurate response."
                style={{ ...inputStyle(), resize: "vertical", lineHeight: 1.6 }}
              />
            </div>

            <div
              style={{
                background: "#eff6ff",
                border: `1px solid #bfdbfe`,
                borderRadius: 8,
                padding: "12px 16px",
                color: "#1e40af",
                fontSize: "0.875rem",
              }}
            >
              ℹ️ By submitting, you acknowledge that this request will be sent
              to the concerned public authority under the Right to Information
              Act.
            </div>

            <div
              style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}
            >
              <Link
                to="/requests"
                style={btnStyle(MUTED, {
                  background: "transparent",
                  border: `1px solid ${BORDER}`,
                  color: TEXT,
                })}
              >
                Cancel
              </Link>
              <button
                type="submit"
                disabled={submitting}
                style={{
                  ...btnStyle(PRIMARY),
                  opacity: submitting ? 0.7 : 1,
                  cursor: submitting ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                {submitting ? (
                  <>
                    <span
                      style={{
                        width: 14,
                        height: 14,
                        border: "2px solid rgba(255,255,255,0.4)",
                        borderTopColor: "#fff",
                        borderRadius: "50%",
                        animation: "spin 0.7s linear infinite",
                        display: "inline-block",
                      }}
                    />
                    Submitting…
                  </>
                ) : (
                  "Submit Request →"
                )}
              </button>
            </div>
          </form>
        </Card>
      </div>
    </PageWrapper>
  );
}

// ─── DepartmentsPage ──────────────────────────────────────────────────────────
function DepartmentsPage() {
  const { data: departments, loading, error } = useFetch("/api/departments");

  return (
    <PageWrapper>
      <PageTitle>Departments</PageTitle>
      <Subtitle>
        Public authorities and government departments you can file RTI requests
        with.
      </Subtitle>

      {loading && <Spinner />}
      {error && (
        <ErrorBanner message={`Failed to load departments: ${error}`} />
      )}

      {departments && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
            gap: 20,
          }}
        >
          {departments.map((dept) => (
            <Card
              key={dept.id}
              style={{ display: "flex", flexDirection: "column", gap: 12 }}
            >
              <div
                style={{ display: "flex", alignItems: "flex-start", gap: 12 }}
              >
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 10,
                    flexShrink: 0,
                    background: `${PRIMARY}18`,
                    color: PRIMARY,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "1.4rem",
                  }}
                >
                  🏛️
                </div>
                <div>
                  <div
                    style={{
                      fontWeight: 700,
                      color: TEXT,
                      fontSize: "1rem",
                      lineHeight: 1.3,
                    }}
                  >
                    {dept.name}
                  </div>
                  {dept.description && (
                    <p
                      style={{
                        color: MUTED,
                        fontSize: "0.875rem",
                        margin: "6px 0 0",
                        lineHeight: 1.6,
                      }}
                    >
                      {dept.description}
                    </p>
                  )}
                </div>
              </div>
              {dept.contact_email && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    paddingTop: 12,
                    borderTop: `1px solid ${BORDER}`,
                    fontSize: "0.85rem",
                    color: MUTED,
                  }}
                >
                  <span>✉️</span>
                  <a
                    href={`mailto:${dept.contact_email}`}
                    style={{ color: PRIMARY, textDecoration: "none" }}
                  >
                    {dept.contact_email}
                  </a>
                </div>
              )}
              <Link
                to={`/requests/new`}
                style={{
                  ...btnStyle(PRIMARY, {
                    padding: "8px 16px",
                    fontSize: "0.8rem",
                    textAlign: "center",
                  }),
                  marginTop: 4,
                }}
              >
                File RTI with this dept →
              </Link>
            </Card>
          ))}
        </div>
      )}
    </PageWrapper>
  );
}

// ─── FaqsPage ─────────────────────────────────────────────────────────────────
function FaqsPage() {
  const { data: faqs, loading, error } = useFetch("/api/faqs");
  const [openId, setOpenId] = useState(null);

  const toggle = (id) => setOpenId((prev) => (prev === id ? null : id));

  return (
    <PageWrapper>
      <PageTitle>Frequently Asked Questions</PageTitle>
      <Subtitle>
        Everything you need to know about filing RTI requests in India.
      </Subtitle>

      {loading && <Spinner />}
      {error && <ErrorBanner message={`Could not load FAQs: ${error}`} />}

      {faqs && (
        <div
          style={{
            maxWidth: 760,
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          {faqs.map((faq, idx) => {
            const isOpen = openId === (faq.id ?? idx);
            return (
              <div
                key={faq.id ?? idx}
                style={{
                  border: `1px solid ${isOpen ? PRIMARY : BORDER}`,
                  borderRadius: 10,
                  overflow: "hidden",
                  boxShadow: isOpen ? `0 0 0 3px ${PRIMARY}22` : "none",
                  transition: "box-shadow 0.2s, border-color 0.2s",
                }}
              >
                <button
                  onClick={() => toggle(faq.id ?? idx)}
                  style={{
                    width: "100%",
                    background: isOpen ? `${PRIMARY}0d` : CARD_BG,
                    border: "none",
                    cursor: "pointer",
                    padding: "18px 20px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                    textAlign: "left",
                    transition: "background 0.15s",
                  }}
                >
                  <span
                    style={{
                      fontWeight: 600,
                      color: isOpen ? PRIMARY : TEXT,
                      fontSize: "0.95rem",
                      lineHeight: 1.5,
                    }}
                  >
                    {faq.question}
                  </span>
                  <span
                    style={{
                      flexShrink: 0,
                      width: 24,
                      height: 24,
                      background: isOpen ? PRIMARY : BORDER,
                      color: isOpen ? "#fff" : MUTED,
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "1rem",
                      fontWeight: 700,
                      transition: "background 0.2s, color 0.2s, transform 0.2s",
                      transform: isOpen ? "rotate(45deg)" : "none",
                    }}
                  >
                    +
                  </span>
                </button>
                {isOpen && (
                  <div
                    style={{
                      padding: "0 20px 20px",
                      borderTop: `1px solid ${BORDER}`,
                      background: CARD_BG,
                    }}
                  >
                    <p
                      style={{
                        margin: "16px 0 0",
                        color: MUTED,
                        lineHeight: 1.75,
                        fontSize: "0.925rem",
                      }}
                    >
                      {faq.answer}
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </PageWrapper>
  );
}

// ─── 404 ──────────────────────────────────────────────────────────────────────
function NotFoundPage() {
  return (
    <PageWrapper>
      <div style={{ textAlign: "center", padding: "80px 0" }}>
        <div style={{ fontSize: "5rem", marginBottom: 16 }}>🔍</div>
        <h1
          style={{
            fontSize: "2rem",
            fontWeight: 800,
            color: TEXT,
            marginBottom: 12,
          }}
        >
          Page Not Found
        </h1>
        <p style={{ color: MUTED, marginBottom: 28 }}>
          The page you're looking for doesn't exist.
        </p>
        <Link to="/" style={btnStyle(PRIMARY)}>
          ← Back to Home
        </Link>
      </div>
    </PageWrapper>
  );
}

// ─── Style helpers ────────────────────────────────────────────────────────────
const tdStyle = { padding: "12px 16px", color: TEXT, verticalAlign: "middle" };

function inputStyle(extra = {}) {
  return {
    padding: "10px 14px",
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    fontSize: "0.9rem",
    color: TEXT,
    background: CARD_BG,
    outline: "none",
    width: "100%",
    boxSizing: "border-box",
    fontFamily: "inherit",
    transition: "border-color 0.15s",
    ...extra,
  };
}

function btnStyle(color, extra = {}) {
  return {
    display: "inline-block",
    background: color,
    color: "#fff",
    fontWeight: 600,
    fontSize: "0.9rem",
    padding: "10px 22px",
    borderRadius: 8,
    textDecoration: "none",
    border: "none",
    cursor: "pointer",
    fontFamily: "inherit",
    lineHeight: 1,
    transition: "background 0.15s",
    ...extra,
  };
}

// ─── Footer ───────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer
      style={{
        borderTop: `1px solid ${BORDER}`,
        background: CARD_BG,
        padding: "28px 24px",
        textAlign: "center",
        color: MUTED,
        fontSize: "0.85rem",
      }}
    >
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <span style={{ fontWeight: 700, color: PRIMARY }}>RTI4All</span>
        {" · "}
        Empowering citizens through transparency
        {" · "}
        Built for Hackathon 2025
      </div>
    </footer>
  );
}

// ─── App (root) ───────────────────────────────────────────────────────────────
export default function App() {
  return (
    <BrowserRouter>
      {/* Global keyframe for spinner */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', system-ui, -apple-system, sans-serif; background: ${BG}; color: ${TEXT}; }
        @keyframes spin { to { transform: rotate(360deg); } }
        a:focus-visible, button:focus-visible { outline: 2px solid ${PRIMARY}; outline-offset: 2px; }
        input:focus, select:focus, textarea:focus { border-color: ${PRIMARY} !important; box-shadow: 0 0 0 3px ${PRIMARY}22; }
      `}</style>

      <Navbar />

      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/requests" element={<RequestsPage />} />
        <Route path="/requests/new" element={<NewRequestPage />} />
        <Route path="/requests/:id" element={<RequestDetailPage />} />
        <Route path="/departments" element={<DepartmentsPage />} />
        <Route path="/faqs" element={<FaqsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>

      <Footer />
    </BrowserRouter>
  );
}
