// Package models defines the in-memory and JSON-serializable shapes used by
// the RTI4All Go backend. They mirror the Pydantic schemas of the original
// Python backend so the React frontend can talk to either drop-in.
package models

// Department describes a public authority citizens can file RTI requests with.
type Department struct {
	ID           string `json:"id"`
	Name         string `json:"name"`
	Description  string `json:"description"`
	ContactEmail string `json:"contact_email"`
}

// FAQ is a frequently asked question about the RTI process.
type FAQ struct {
	ID       string `json:"id"`
	Question string `json:"question"`
	Answer   string `json:"answer"`
}

// ProcessedRequestData is the AI-extracted structured view of a citizen request.
// All fields are optional / best-effort; we use map[string]any everywhere we
// store it so it round-trips JSON faithfully even if the AI returns extra keys.

// ClarificationRequest is the officer-to-citizen ask for more info.
type ClarificationRequest struct {
	Message               string   `json:"message"`
	MissingFields         []string `json:"missing_fields,omitempty"`
	Questions             []string `json:"questions,omitempty"`
	SuggestedImprovements []string `json:"suggested_improvements,omitempty"`
}

// RTIRequest is the full record (admin view). The frontend's public view is
// just a subset of these fields; we keep one struct internally and let the
// HTTP layer choose which fields to expose.
//
// We use a flat map[string]any model for processed_data and clarification
// records to keep parity with the Python backend where the AI returns
// arbitrary nested JSON.
type RTIRequest struct {
	ID              string `json:"id"`
	CitizenName     string `json:"citizen_name"`
	Email           string `json:"email"`
	CitizenPhone    string `json:"citizen_phone,omitempty"`
	CitizenAddress  string `json:"citizen_address,omitempty"`
	CitizenIDCard   string `json:"citizen_id_card,omitempty"`
	DepartmentID    string `json:"department_id"`
	Department      string `json:"department"`
	Subject         string `json:"subject"`
	Description     string `json:"description"`
	Status          string `json:"status"`
	DateFiled       string `json:"date_filed"`
	DateUpdated     string `json:"date_updated"`
	Response        string `json:"response,omitempty"`
	ReviewedBy      string `json:"reviewed_by,omitempty"`
	ReviewedAt      string `json:"reviewed_at,omitempty"`
	RejectionReason string `json:"rejection_reason,omitempty"`

	ProcessedData          map[string]any   `json:"processed_data,omitempty"`
	ClarificationRequested map[string]any   `json:"clarification_requested,omitempty"`
	ClarificationHistory   []map[string]any `json:"clarification_history"`
	CitizenUpdates         []map[string]any `json:"citizen_updates"`
}

// DB is the top-level on-disk store. Mirrors backend/data/sample_data.json.
type DB struct {
	Departments []Department  `json:"departments"`
	Requests    []*RTIRequest `json:"requests"`
	FAQs        []FAQ         `json:"faqs"`
}

// PublicRequest is the citizen-facing view of an RTIRequest. It hides the
// snapshotted profile fields and the internal review audit trail.
type PublicRequest struct {
	ID                     string           `json:"id"`
	CitizenName            string           `json:"citizen_name"`
	Email                  string           `json:"email"`
	DepartmentID           string           `json:"department_id"`
	Department             string           `json:"department"`
	Subject                string           `json:"subject"`
	Description            string           `json:"description"`
	Status                 string           `json:"status"`
	DateFiled              string           `json:"date_filed"`
	DateUpdated            string           `json:"date_updated"`
	Response               string           `json:"response,omitempty"`
	RejectionReason        string           `json:"rejection_reason,omitempty"`
	ProcessedData          map[string]any   `json:"processed_data,omitempty"`
	ClarificationRequested map[string]any   `json:"clarification_requested,omitempty"`
	ClarificationHistory   []map[string]any `json:"clarification_history"`
	CitizenUpdates         []map[string]any `json:"citizen_updates"`
}

// ToPublic projects an RTIRequest into the citizen-facing view.
func (r *RTIRequest) ToPublic() *PublicRequest {
	return &PublicRequest{
		ID:                     r.ID,
		CitizenName:            r.CitizenName,
		Email:                  r.Email,
		DepartmentID:           r.DepartmentID,
		Department:             r.Department,
		Subject:                r.Subject,
		Description:            r.Description,
		Status:                 r.Status,
		DateFiled:              r.DateFiled,
		DateUpdated:            r.DateUpdated,
		Response:               r.Response,
		RejectionReason:        r.RejectionReason,
		ProcessedData:          r.ProcessedData,
		ClarificationRequested: r.ClarificationRequested,
		ClarificationHistory:   nonNilMaps(r.ClarificationHistory),
		CitizenUpdates:         nonNilMaps(r.CitizenUpdates),
	}
}

func nonNilMaps(v []map[string]any) []map[string]any {
	if v == nil {
		return []map[string]any{}
	}
	return v
}
