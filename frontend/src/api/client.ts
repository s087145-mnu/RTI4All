// A thin typed wrapper around fetch that knows about the RTI4All API.
//
// - prefixes every URL with /api so callers can write resource paths
// - injects the bearer token when one is supplied
// - parses JSON and normalises errors into ApiError for the UI to render
// - on 401, fires a window event so the AuthProvider can clear local state

import type {
  AdminRequest,
  AdminUpdatePayload,
  AuthResponse,
  CitizenClarifyPayload,
  CreateRequestPayload,
  Department,
  FAQ,
  LoginPayload,
  PublicRequest,
  SignupPayload,
  Stats,
  UserPublic,
} from "@/types/api";

const API_PREFIX = "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

/** Custom event emitted when the API returns 401 — AuthProvider listens. */
export const UNAUTHORIZED_EVENT = "rti4all:unauthorized";

function extractDetail(body: unknown, fallback: string): string {
  if (typeof body !== "object" || body === null) return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (typeof d === "object" && d !== null) {
          const loc = (d as { loc?: unknown[] }).loc ?? [];
          const msg = (d as { msg?: string }).msg ?? "";
          return `${loc.join(".")}: ${msg}`;
        }
        return String(d);
      })
      .join("; ");
  }
  return fallback;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string | null;
  query?: Record<string, string | undefined>;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token, query } = opts;

  let url = API_PREFIX + path;
  if (query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") params.set(k, v);
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
  }

  // 204 has no body; treat as void.
  if (res.status === 204) {
    return undefined as unknown as T;
  }

  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(extractDetail(payload, `HTTP ${res.status}`), res.status);
  }
  return payload as T;
}

// ---------------------------------------------------------------------------
// Public route bindings
// ---------------------------------------------------------------------------

export const api = {
  // Auth
  signup: (payload: SignupPayload) =>
    request<AuthResponse>("/auth/signup", { method: "POST", body: payload }),
  login: (payload: LoginPayload) =>
    request<AuthResponse>("/auth/login", { method: "POST", body: payload }),
  me: (token: string) => request<UserPublic>("/auth/me", { token }),

  // Departments / FAQs / stats
  departments: () => request<Department[]>("/departments"),
  department: (id: string) => request<Department>(`/departments/${id}`),
  faqs: () => request<FAQ[]>("/faqs"),
  stats: () => request<Stats>("/stats"),

  // Citizen requests
  listMyRequests: (
    token: string,
    filters?: { status?: string; department_id?: string },
  ) =>
    request<PublicRequest[]>("/requests", { token, query: filters }),
  getRequest: (token: string, id: string) =>
    request<PublicRequest>(`/requests/${id}`, { token }),
  createRequest: (token: string, payload: CreateRequestPayload) =>
    request<AdminRequest>("/requests", {
      method: "POST",
      body: payload,
      token,
    }),
  citizenClarify: (
    token: string,
    id: string,
    payload: CitizenClarifyPayload,
  ) =>
    request<PublicRequest>(`/requests/${id}/clarify`, {
      method: "PATCH",
      body: payload,
      token,
    }),

  // Admin
  adminPending: (token: string) =>
    request<AdminRequest[]>("/admin/requests/pending", { token }),
  adminGetRequest: (token: string, id: string) =>
    request<AdminRequest>(`/admin/requests/${id}`, { token }),
  adminUpdateRequest: (token: string, id: string, payload: AdminUpdatePayload) =>
    request<AdminRequest>(`/admin/requests/${id}`, {
      method: "PATCH",
      body: payload,
      token,
    }),
};
