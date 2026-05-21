// Package handlers wires the HTTP layer to the application's state and
// services. It exposes a single Server struct that owns the shared db, auth
// service, AI client, and retrieval indexes, and registers chi routes that
// mirror the original FastAPI surface byte-for-byte.
package handlers

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/rti4all/backend-go/internal/ai"
	"github.com/rti4all/backend-go/internal/auth"
	"github.com/rti4all/backend-go/internal/cache"
	"github.com/rti4all/backend-go/internal/graph"
	"github.com/rti4all/backend-go/internal/models"
	"github.com/rti4all/backend-go/internal/persistence"
	"github.com/rti4all/backend-go/internal/rag"
)

// Server is the dependency container for HTTP routes. Everything that needs
// to be reachable from a handler lives on this struct.
type Server struct {
	mu sync.RWMutex // protects DB.Requests mutations

	DB        *models.DB
	Auth      *auth.Service
	AI        *ai.Client
	Cache     *cache.Cache
	RAG       *rag.Index
	Graph     *graph.State
	Persistor *persistence.Store
}

// adminEditableStatuses lists the values the admin update endpoint accepts
// for the status field.
var adminEditableStatuses = map[string]struct{}{
	"Under Review":         {},
	"Responded":            {},
	"Rejected":             {},
	"Pending":              {},
	"Clarification Needed": {},
}

// ----------------------------------------------------------------------------
// Route registration
// ----------------------------------------------------------------------------

// Routes returns a chi router with every API endpoint installed.
func (s *Server) Routes() http.Handler {
	r := chi.NewRouter()

	r.Get("/api/health", s.health)

	// Auth
	r.Post("/api/auth/signup", s.signup)
	r.Post("/api/auth/login", s.login)
	r.With(s.Auth.RequireAuth).Get("/api/auth/me", s.me)

	// Departments + FAQs (public)
	r.Get("/api/departments", s.listDepartments)
	r.Get("/api/departments/{id}", s.getDepartment)
	r.Get("/api/faqs", s.listFAQs)

	// Stats (public — same as Python)
	r.Get("/api/stats", s.getStats)
	// Public feed — anonymous responded requests are excluded.
	r.Get("/api/public/requests", s.listPublicRequests)

	// Citizen request routes
	r.With(s.Auth.RequireAuth).Get("/api/requests", s.listRequests)
	r.With(s.Auth.RequireAuth).Post("/api/requests", s.createRequest)
	r.With(s.Auth.RequireAuth).Get("/api/requests/{id}", s.getRequest)
	r.With(s.Auth.RequireAuth).Patch("/api/requests/{id}/clarify", s.citizenClarify)

	// Admin routes
	r.With(s.Auth.RequireAdmin).Get("/api/admin/requests/pending", s.adminListPending)
	r.With(s.Auth.RequireAdmin).Get("/api/admin/requests/{id}", s.adminGetRequest)
	r.With(s.Auth.RequireAdmin).Patch("/api/admin/requests/{id}", s.adminUpdateRequest)

	return r
}

// ----------------------------------------------------------------------------
// Response helpers
// ----------------------------------------------------------------------------

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(body); err != nil {
		log.Printf("[handlers] encode: %v", err)
	}
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"detail": msg})
}

// ----------------------------------------------------------------------------
// Meta
// ----------------------------------------------------------------------------

func (s *Server) health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// ----------------------------------------------------------------------------
// Auth
// ----------------------------------------------------------------------------

func (s *Server) signup(w http.ResponseWriter, r *http.Request) {
	var req auth.SignupRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid JSON body.")
		return
	}
	user, err := s.Auth.CreateUser(req)
	if err != nil {
		switch {
		case errors.Is(err, auth.ErrUserExists):
			writeError(w, http.StatusConflict, "A user with this email already exists.")
		case errors.Is(err, auth.ErrMissingField):
			writeError(w, http.StatusUnprocessableEntity, err.Error())
		default:
			writeError(w, http.StatusInternalServerError, "Could not create user.")
		}
		return
	}
	token, err := s.Auth.CreateAccessToken(user)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Could not issue token.")
		return
	}
	writeJSON(w, http.StatusCreated, auth.AuthResponse{
		AccessToken: token,
		TokenType:   "bearer",
		User:        user,
	})
}

func (s *Server) login(w http.ResponseWriter, r *http.Request) {
	var req auth.LoginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid JSON body.")
		return
	}
	user, err := s.Auth.Authenticate(req.Email, req.Password)
	if err != nil {
		writeError(w, http.StatusUnauthorized, "Invalid email or password.")
		return
	}
	token, err := s.Auth.CreateAccessToken(user)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Could not issue token.")
		return
	}
	writeJSON(w, http.StatusOK, auth.AuthResponse{
		AccessToken: token,
		TokenType:   "bearer",
		User:        user,
	})
}

func (s *Server) me(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.FromContext(r.Context())
	writeJSON(w, http.StatusOK, user)
}

// ----------------------------------------------------------------------------
// Departments + FAQs
// ----------------------------------------------------------------------------

func (s *Server) listDepartments(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	writeJSON(w, http.StatusOK, s.DB.Departments)
}

func (s *Server) getDepartment(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	s.mu.RLock()
	defer s.mu.RUnlock()
	for _, d := range s.DB.Departments {
		if d.ID == id {
			writeJSON(w, http.StatusOK, d)
			return
		}
	}
	writeError(w, http.StatusNotFound, fmt.Sprintf("Department '%s' not found.", id))
}

func (s *Server) listFAQs(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	writeJSON(w, http.StatusOK, s.DB.FAQs)
}

// ----------------------------------------------------------------------------
// Stats
// ----------------------------------------------------------------------------

func (s *Server) getStats(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	counts := map[string]int{
		"Pending":              0,
		"In Progress":          0,
		"Under Review":         0,
		"Clarification Needed": 0,
		"Responded":            0,
		"Rejected":             0,
	}
	for _, req := range s.DB.Requests {
		if _, ok := counts[req.Status]; ok {
			counts[req.Status]++
		}
	}
	writeJSON(w, http.StatusOK, map[string]int{
		"total_requests":       len(s.DB.Requests),
		"pending":              counts["Pending"],
		"in_progress":          counts["In Progress"],
		"under_review":         counts["Under Review"],
		"clarification_needed": counts["Clarification Needed"],
		"responded":            counts["Responded"],
		"rejected":             counts["Rejected"],
		"total_departments":    len(s.DB.Departments),
	})
}

// ----------------------------------------------------------------------------
// Citizen request routes
// ----------------------------------------------------------------------------

func (s *Server) listRequests(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.FromContext(r.Context())
	statusFilter := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("status")))
	deptFilter := strings.TrimSpace(r.URL.Query().Get("department_id"))

	s.mu.RLock()
	defer s.mu.RUnlock()

	results := make([]*models.PublicRequest, 0)
	for _, req := range s.DB.Requests {
		if !user.IsAdmin && !strings.EqualFold(req.Email, user.Email) {
			continue
		}
		if statusFilter != "" && !strings.EqualFold(req.Status, statusFilter) {
			continue
		}
		if deptFilter != "" && req.DepartmentID != deptFilter {
			continue
		}
		results = append(results, req.ToPublic())
	}
	writeJSON(w, http.StatusOK, results)
}

func (s *Server) getRequest(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.FromContext(r.Context())
	id := chi.URLParam(r, "id")

	s.mu.RLock()
	defer s.mu.RUnlock()

	for _, req := range s.DB.Requests {
		if req.ID == id {
			if !user.IsAdmin && !strings.EqualFold(req.Email, user.Email) {
				writeError(w, http.StatusForbidden, "You do not have permission to access this request.")
				return
			}
			writeJSON(w, http.StatusOK, req.ToPublic())
			return
		}
	}
	writeError(w, http.StatusNotFound, fmt.Sprintf("RTI request '%s' not found.", id))
}

type createRequestPayload struct {
	DepartmentID string `json:"department_id"`
	Subject      string `json:"subject"`
	Description  string `json:"description"`
	// Visibility is "public" (default) or "anonymous". Anonymous requests are
	// hidden from the public homepage feed even after they're responded to.
	Visibility string `json:"visibility"`
}

// listPublicRequests returns the most recent N responded RTI requests whose
// visibility is "public" (or unset, treated as public). Used by the homepage
// hero to show a real, anonymised feed of resolved cases.
func (s *Server) listPublicRequests(w http.ResponseWriter, r *http.Request) {
	limit := 5
	if v := r.URL.Query().Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 && n <= 50 {
			limit = n
		}
	}

	s.mu.RLock()
	defer s.mu.RUnlock()

	// Collect responded + public, newest first by date_updated.
	candidates := make([]*models.RTIRequest, 0)
	for _, req := range s.DB.Requests {
		if req.Status != "Responded" || req.IsAnonymous() {
			continue
		}
		candidates = append(candidates, req)
	}
	sort.Slice(candidates, func(i, j int) bool {
		if candidates[i].DateUpdated != candidates[j].DateUpdated {
			return candidates[i].DateUpdated > candidates[j].DateUpdated
		}
		return candidates[i].ID > candidates[j].ID
	})
	if limit > len(candidates) {
		limit = len(candidates)
	}

	// Shape a minimal payload — we deliberately omit `citizen_name` and
	// `email` here so the public feed never doxxes filers, even on "public"
	// requests.
	type publicListing struct {
		ID          string `json:"id"`
		Subject     string `json:"subject"`
		Department  string `json:"department"`
		DateUpdated string `json:"date_updated"`
		Response    string `json:"response"`
	}
	out := make([]publicListing, 0, limit)
	for _, req := range candidates[:limit] {
		out = append(out, publicListing{
			ID:          req.ID,
			Subject:     req.Subject,
			Department:  req.Department,
			DateUpdated: req.DateUpdated,
			Response:    req.Response,
		})
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) createRequest(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.FromContext(r.Context())

	var p createRequestPayload
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid JSON body.")
		return
	}
	p.DepartmentID = strings.TrimSpace(p.DepartmentID)
	p.Subject = strings.TrimSpace(p.Subject)
	p.Description = strings.TrimSpace(p.Description)
	if p.DepartmentID == "" || p.Subject == "" || p.Description == "" {
		writeError(w, http.StatusUnprocessableEntity, "department_id, subject, and description are required.")
		return
	}

	deptName, ok := s.lookupDepartmentName(p.DepartmentID)
	if !ok {
		writeError(w, http.StatusNotFound, fmt.Sprintf("Department with id '%s' not found.", p.DepartmentID))
		return
	}

	today := time.Now().Format("2006-01-02")

	// Step 1: structure the request for officer review.
	log.Printf("[handlers] processing new request: %q", trim(p.Subject, 50))
	processed := s.AI.ProcessRequestStructure(r.Context(), p.Subject, p.Description, p.DepartmentID)

	// Step 2: if the request looks complete, generate an AI draft.
	answer := ""
	requestStatus := "Under Review"
	if score, ok := completenessScore(processed); ok && score >= 0.7 {
		drafted, status := s.generateAnswer(r, p.DepartmentID, p.Subject, p.Description)
		answer = drafted
		requestStatus = status
	} else {
		log.Printf("[handlers] request needs officer review (completeness below 0.7)")
	}

	visibility := strings.ToLower(strings.TrimSpace(p.Visibility))
	if visibility != "anonymous" {
		visibility = "public"
	}

	newReq := &models.RTIRequest{
		ID:                   s.nextRequestID(),
		CitizenName:          user.FullName,
		Email:                user.Email,
		CitizenPhone:         user.PhoneNumber,
		CitizenAddress:       user.PresentAddress,
		CitizenIDCard:        user.IDCard,
		DepartmentID:         p.DepartmentID,
		Department:           deptName,
		Subject:              p.Subject,
		Description:          p.Description,
		Status:               requestStatus,
		DateFiled:            today,
		DateUpdated:          today,
		Response:             answer,
		Visibility:           visibility,
		ProcessedData:        processed,
		ClarificationHistory: []map[string]any{},
		CitizenUpdates:       []map[string]any{},
	}

	s.mu.Lock()
	s.DB.Requests = append(s.DB.Requests, newReq)
	s.mu.Unlock()

	s.persistInBackground()
	writeJSON(w, http.StatusCreated, newReq)
}

type citizenClarifyPayload struct {
	UpdatedDescription    string            `json:"updated_description"`
	AdditionalInformation string            `json:"additional_information"`
	AnswersToQuestions    map[string]string `json:"answers_to_questions"`
}

func (s *Server) citizenClarify(w http.ResponseWriter, r *http.Request) {
	user, _ := auth.FromContext(r.Context())
	id := chi.URLParam(r, "id")

	var p citizenClarifyPayload
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid JSON body.")
		return
	}

	s.mu.Lock()
	var target *models.RTIRequest
	for _, req := range s.DB.Requests {
		if req.ID == id {
			target = req
			break
		}
	}
	if target == nil {
		s.mu.Unlock()
		writeError(w, http.StatusNotFound, fmt.Sprintf("RTI request '%s' not found.", id))
		return
	}
	if !strings.EqualFold(target.Email, user.Email) {
		s.mu.Unlock()
		writeError(w, http.StatusForbidden, "You can only update your own requests.")
		return
	}
	if target.Status != "Clarification Needed" {
		s.mu.Unlock()
		writeError(w, http.StatusBadRequest, "No clarification has been requested for this request.")
		return
	}

	answers := map[string]any{}
	for k, v := range p.AnswersToQuestions {
		answers[k] = v
	}
	target.CitizenUpdates = append(target.CitizenUpdates, map[string]any{
		"timestamp":              time.Now().Format("2006-01-02"),
		"updated_description":    p.UpdatedDescription,
		"additional_information": p.AdditionalInformation,
		"answers_to_questions":   answers,
	})

	if strings.TrimSpace(p.UpdatedDescription) != "" {
		target.Description = p.UpdatedDescription
	}
	target.ClarificationRequested = nil
	target.Status = "Under Review"
	target.DateUpdated = time.Now().Format("2006-01-02")

	subject := target.Subject
	description := target.Description
	deptID := target.DepartmentID
	s.mu.Unlock()

	// Re-process the request asynchronously of the lock so other reads aren't
	// blocked on the AI round-trip.
	processed := s.AI.ProcessRequestStructure(r.Context(), subject, description, deptID)

	s.mu.Lock()
	target.ProcessedData = processed
	s.mu.Unlock()

	s.persistInBackground()
	writeJSON(w, http.StatusOK, target.ToPublic())
}

// ----------------------------------------------------------------------------
// Admin routes
// ----------------------------------------------------------------------------

func (s *Server) adminListPending(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	pending := make([]*models.RTIRequest, 0)
	for _, req := range s.DB.Requests {
		if req.Status == "Under Review" {
			pending = append(pending, req)
		}
	}
	sort.Slice(pending, func(i, j int) bool {
		if pending[i].DateFiled != pending[j].DateFiled {
			return pending[i].DateFiled < pending[j].DateFiled
		}
		return pending[i].ID < pending[j].ID
	})
	writeJSON(w, http.StatusOK, pending)
}

func (s *Server) adminGetRequest(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	s.mu.RLock()
	defer s.mu.RUnlock()
	for _, req := range s.DB.Requests {
		if req.ID == id {
			writeJSON(w, http.StatusOK, req)
			return
		}
	}
	writeError(w, http.StatusNotFound, fmt.Sprintf("RTI request '%s' not found.", id))
}

type adminUpdatePayload struct {
	Response             *string                      `json:"response"`
	Status               *string                      `json:"status"`
	RejectionReason      *string                      `json:"rejection_reason"`
	RequestClarification *models.ClarificationRequest `json:"request_clarification"`
}

func (s *Server) adminUpdateRequest(w http.ResponseWriter, r *http.Request) {
	admin, _ := auth.FromContext(r.Context())
	id := chi.URLParam(r, "id")

	var p adminUpdatePayload
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid JSON body.")
		return
	}

	s.mu.Lock()
	var target *models.RTIRequest
	for _, req := range s.DB.Requests {
		if req.ID == id {
			target = req
			break
		}
	}
	if target == nil {
		s.mu.Unlock()
		writeError(w, http.StatusNotFound, fmt.Sprintf("RTI request '%s' not found.", id))
		return
	}
	today := time.Now().Format("2006-01-02")

	// Officer-driven clarification request takes priority and is handled as a
	// distinct flow (matches the Python branch).
	if p.RequestClarification != nil {
		clar := map[string]any{
			"message":                p.RequestClarification.Message,
			"missing_fields":         stringsToAny(p.RequestClarification.MissingFields),
			"questions":              stringsToAny(p.RequestClarification.Questions),
			"suggested_improvements": stringsToAny(p.RequestClarification.SuggestedImprovements),
		}
		target.ClarificationHistory = append(target.ClarificationHistory, map[string]any{
			"timestamp":     today,
			"requested_by":  admin.Email,
			"clarification": clar,
		})
		target.ClarificationRequested = clar
		target.Status = "Clarification Needed"
		target.DateUpdated = today
		target.ReviewedBy = admin.Email
		target.ReviewedAt = today
		s.mu.Unlock()

		s.persistInBackground()
		writeJSON(w, http.StatusOK, target)
		return
	}

	if p.Response == nil && p.Status == nil && p.RejectionReason == nil {
		s.mu.Unlock()
		writeError(w, http.StatusBadRequest,
			"At least one of response, status, rejection_reason, or request_clarification must be provided.")
		return
	}

	if p.Status != nil {
		if _, ok := adminEditableStatuses[*p.Status]; !ok {
			s.mu.Unlock()
			writeError(w, http.StatusBadRequest,
				fmt.Sprintf("Invalid status '%s'.", *p.Status))
			return
		}
		target.Status = *p.Status
	}
	if p.Response != nil {
		target.Response = *p.Response
	}
	if p.RejectionReason != nil {
		target.RejectionReason = *p.RejectionReason
	}
	target.DateUpdated = today
	target.ReviewedBy = admin.Email
	target.ReviewedAt = today

	// Snapshot the request value so we can update retrieval indexes outside
	// of the write lock without racing the caller.
	snapshot := *target
	s.mu.Unlock()

	if snapshot.Status == "Responded" {
		rag.IndexResponded(s.RAG, &snapshot)
		s.Graph.UpdateForRequest(&snapshot)
	}

	s.persistInBackground()
	writeJSON(w, http.StatusOK, target)
}

// ----------------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------------

// nextRequestID generates the next sequential id of the form RTI-YYYY-NNNN.
func (s *Server) nextRequestID() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	maxSeq := 0
	for _, r := range s.DB.Requests {
		parts := strings.Split(r.ID, "-")
		if len(parts) == 0 {
			continue
		}
		seq, err := strconv.Atoi(parts[len(parts)-1])
		if err == nil && seq > maxSeq {
			maxSeq = seq
		}
	}
	return fmt.Sprintf("RTI-%d-%04d", time.Now().Year(), maxSeq+1)
}

func (s *Server) lookupDepartmentName(id string) (string, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	for _, d := range s.DB.Departments {
		if d.ID == id {
			return d.Name, true
		}
	}
	return "", false
}

func (s *Server) generateAnswer(r *http.Request, deptID, subject, description string) (string, string) {
	key := cache.MakeKey(deptID, subject, description)
	if cached, ok := s.Cache.Get(key); ok {
		log.Printf("[handlers] cache hit for %q", trim(subject, 50))
		return cached, "Under Review"
	}
	answer, err := s.AI.AnswerRequest(r.Context(), subject, description, s.RAG, s.Graph)
	if err != nil {
		log.Printf("[handlers] ai draft failed: %v", err)
		return "", "Pending"
	}
	if strings.TrimSpace(answer) == "" {
		return "", "Pending"
	}
	s.Cache.Put(key, answer)
	return answer, "Under Review"
}

func (s *Server) persistInBackground() {
	if s.Persistor == nil {
		return
	}
	go func() {
		s.mu.RLock()
		// Take a shallow copy of the DB pointer; persistence reads from the
		// live structs but JSON encoding is safe under the read lock.
		err := s.Persistor.Save(s.DB)
		s.mu.RUnlock()
		if err != nil {
			log.Printf("[handlers] persist failed: %v", err)
		}
	}()
}

func completenessScore(p map[string]any) (float64, bool) {
	if p == nil {
		return 0, false
	}
	switch v := p["completeness_score"].(type) {
	case float64:
		return v, true
	case float32:
		return float64(v), true
	case int:
		return float64(v), true
	case int64:
		return float64(v), true
	}
	return 0, false
}

func stringsToAny(in []string) []any {
	out := make([]any, len(in))
	for i, v := range in {
		out[i] = v
	}
	return out
}

func trim(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}
