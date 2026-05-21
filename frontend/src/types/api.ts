// Wire-level types that mirror the Go backend's JSON shapes.
//
// Field names use snake_case to match the API contract so we can avoid a
// transformation layer.

export interface UserPublic {
  email: string;
  full_name: string;
  present_address: string;
  phone_number: string;
  id_card?: string;
  is_admin: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserPublic;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface SignupPayload extends LoginPayload {
  full_name: string;
  present_address: string;
  phone_number: string;
  id_card?: string;
}

export interface Department {
  id: string;
  name: string;
  description: string;
  contact_email: string;
}

export interface FAQ {
  id: string;
  question: string;
  answer: string;
}

export type RequestStatus =
  | "Pending"
  | "In Progress"
  | "Under Review"
  | "Clarification Needed"
  | "Responded"
  | "Rejected";

/** AI-extracted analysis of a citizen request (free-form by design). */
export type ProcessedData = Record<string, unknown> & {
  request_type?: string;
  key_questions?: string[];
  information_sought?: string[];
  time_period?: string | null;
  geographic_scope?: string | null;
  urgency_indicators?: string[];
  completeness_score?: number;
  missing_information?: string[];
  related_policies?: string[];
  estimated_complexity?: "Simple" | "Moderate" | "Complex" | string;
  suggested_response_approach?: string;
  relevant_precedents?: string[];
};

export interface ClarificationRequest {
  message: string;
  missing_fields?: string[];
  questions?: string[];
  suggested_improvements?: string[];
}

export interface ClarificationHistoryEntry {
  timestamp: string;
  requested_by: string;
  clarification: ClarificationRequest;
}

export interface CitizenUpdateEntry {
  timestamp: string;
  updated_description?: string;
  additional_information?: string;
  answers_to_questions?: Record<string, string>;
}

/** Citizen-facing projection of an RTI request (no profile snapshot, no audit). */
export interface PublicRequest {
  id: string;
  citizen_name: string;
  email: string;
  department_id: string;
  department: string;
  subject: string;
  description: string;
  status: RequestStatus;
  date_filed: string;
  date_updated: string;
  response?: string;
  rejection_reason?: string;
  processed_data?: ProcessedData;
  clarification_requested?: ClarificationRequest;
  clarification_history?: ClarificationHistoryEntry[];
  citizen_updates?: CitizenUpdateEntry[];
}

/** Admin view — adds the citizen profile snapshot + review audit. */
export interface AdminRequest extends PublicRequest {
  citizen_phone?: string;
  citizen_address?: string;
  citizen_id_card?: string;
  reviewed_by?: string;
  reviewed_at?: string;
}

export interface CreateRequestPayload {
  department_id: string;
  subject: string;
  description: string;
}

export interface AdminUpdatePayload {
  response?: string;
  status?: RequestStatus;
  rejection_reason?: string;
  request_clarification?: ClarificationRequest;
}

export interface CitizenClarifyPayload {
  updated_description?: string;
  additional_information?: string;
  answers_to_questions?: Record<string, string>;
}

export interface Stats {
  total_requests: number;
  pending: number;
  in_progress: number;
  under_review: number;
  clarification_needed: number;
  responded: number;
  rejected: number;
  total_departments: number;
}
