// Package ai talks to the Anthropic Messages API to (a) structure a freshly
// filed citizen request for officer review and (b) draft a citizen-facing
// response grounded in the ministry archive.
//
// The Go port uses the Anthropic REST API directly over net/http — no SDK —
// to keep the dependency surface tiny.
//
// Web search/fetch tools (used by the Python AI step) are intentionally NOT
// wired up here. They are an optional grounding source; the local archive
// retrieval (RAG + graph) is the primary signal and produces high-quality
// drafts on its own.
package ai

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/rti4all/backend-go/internal/graph"
	"github.com/rti4all/backend-go/internal/rag"
)

// Client is a thin Anthropic Messages-API client.
type Client struct {
	APIKey     string
	Model      string
	HTTPClient *http.Client
}

// New constructs an AI client. An empty API key is allowed — calls will
// short-circuit with a stub response, mirroring the Python behaviour.
func New() *Client {
	model := os.Getenv("ANTHROPIC_MODEL")
	if model == "" {
		// claude-haiku-4-5 was the Python default; pin to the same model.
		model = "claude-haiku-4-5"
	}
	return &Client{
		APIKey:     strings.TrimSpace(os.Getenv("ANTHROPIC_API_KEY")),
		Model:      model,
		HTTPClient: &http.Client{Timeout: 60 * time.Second},
	}
}

// Configured reports whether the client has a usable API key.
func (c *Client) Configured() bool {
	return c.APIKey != "" && !strings.HasPrefix(c.APIKey, "sk-ant-placeholder")
}

// ----------------------------------------------------------------------------
// Anthropic API plumbing
// ----------------------------------------------------------------------------

type apiMessageRequest struct {
	Model     string       `json:"model"`
	MaxTokens int          `json:"max_tokens"`
	System    string       `json:"system,omitempty"`
	Messages  []apiMessage `json:"messages"`
}

type apiMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type apiMessageResponse struct {
	ID      string `json:"id"`
	Type    string `json:"type"`
	Role    string `json:"role"`
	Content []struct {
		Type string `json:"type"`
		Text string `json:"text"`
	} `json:"content"`
	StopReason string `json:"stop_reason"`
	Error      *struct {
		Type    string `json:"type"`
		Message string `json:"message"`
	} `json:"error,omitempty"`
}

func (c *Client) callMessages(ctx context.Context, req apiMessageRequest) (string, error) {
	if !c.Configured() {
		return "", fmt.Errorf("anthropic API key not configured")
	}
	body, err := json.Marshal(req)
	if err != nil {
		return "", fmt.Errorf("marshal request: %w", err)
	}
	httpReq, err := http.NewRequestWithContext(ctx, "POST", "https://api.anthropic.com/v1/messages", bytes.NewReader(body))
	if err != nil {
		return "", fmt.Errorf("build request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("x-api-key", c.APIKey)
	httpReq.Header.Set("anthropic-version", "2023-06-01")

	resp, err := c.HTTPClient.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("anthropic call: %w", err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("read response: %w", err)
	}
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("anthropic returned HTTP %d: %s", resp.StatusCode, string(raw))
	}
	var parsed apiMessageResponse
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return "", fmt.Errorf("decode response: %w", err)
	}
	if parsed.Error != nil {
		return "", fmt.Errorf("anthropic error: %s: %s", parsed.Error.Type, parsed.Error.Message)
	}
	var text strings.Builder
	for _, block := range parsed.Content {
		if block.Type == "text" {
			if text.Len() > 0 {
				text.WriteString("\n\n")
			}
			text.WriteString(strings.TrimSpace(block.Text))
		}
	}
	return text.String(), nil
}

// ----------------------------------------------------------------------------
// Drafting a citizen-facing response
// ----------------------------------------------------------------------------

const answerSystemTemplate = `You are an AI assistant for the Maldives Ministry of Climate Change, Environment and Energy's citizen Right to Information (RTI) portal.

When a citizen submits an RTI request, your job is to draft a clear, factual response addressed to the citizen, grounded in the ministry's local archive of past responded RTI requests and standing FAQs.

The archive is retrieved for you two ways and shown below:
  - Vector matches: items semantically similar to the question.
  - Graph-linked items: items that share key concepts with the question.

These are authoritative precedent and process knowledge. PREFER them when they answer the question.

If the archive does not contain enough information to answer fully, say so plainly and direct the citizen to file a formal follow-up RTI application with the Information Officer specifying the missing detail.

MINISTRY ARCHIVE — VECTOR MATCHES:
%s

MINISTRY ARCHIVE — GRAPH-LINKED PRECEDENT:
%s

RULES:
- Every factual claim must come from the archive shown above. Do not invent figures, names, dates, or document references.
- Cite the relevant prior RTI id (e.g. RTI-2024-0001) or FAQ id when you draw on it.
- Address the citizen directly. Be concise: 4-8 sentences, plain prose, no markdown headings.

OUTPUT FORMAT:
Your reply will be shown to the citizen verbatim. Do NOT include any preamble or signoff like "Response to Citizen:", "Dear Citizen,", or "Best regards". Output ONLY the body of the response, in plain prose, starting with the substantive answer.`

// AnswerRequest drafts a citizen-facing response to a new RTI request.
//
// It assembles the ministry-archive context block from RAG + graph hits and
// asks Claude for a 4-8 sentence answer. If the AI key isn't configured, it
// returns a clearly-labelled stub so the rest of the flow still works in
// local development.
func (c *Client) AnswerRequest(ctx context.Context, subject, description string, ragIdx *rag.Index, graphState *graph.State) (string, error) {
	if !c.Configured() {
		log.Println("[ai] ANTHROPIC_API_KEY not set; returning stub response")
		return "[AI service not configured: set ANTHROPIC_API_KEY] Your request to the Ministry of Climate Change, Environment and Energy has been received and is pending review.", nil
	}

	query := strings.TrimSpace(subject + "\n" + description)

	const ragK = 4
	const graphK = 3

	var vectorHits []rag.Hit
	if ragIdx != nil {
		vectorHits = ragIdx.Retrieve(query, ragK)
	}

	var graphHits []rag.Hit
	if graphState != nil {
		graphHits = graphState.Retrieve(query, graphK+ragK)
	}
	// Dedupe graph hits against vector hits to keep the prompt compact.
	seen := map[string]struct{}{}
	for _, h := range vectorHits {
		if id, ok := h.Payload["id"].(string); ok {
			seen[id] = struct{}{}
		}
	}
	deduped := make([]rag.Hit, 0, len(graphHits))
	for _, h := range graphHits {
		id, _ := h.Payload["id"].(string)
		if _, dup := seen[id]; dup {
			continue
		}
		deduped = append(deduped, h)
		if len(deduped) >= graphK {
			break
		}
	}

	system := fmt.Sprintf(answerSystemTemplate,
		rag.FormatForPrompt(vectorHits),
		graph.FormatForPrompt(deduped),
	)

	userPrompt := fmt.Sprintf("Subject: %s\nDescription: %s\n\nGround your draft in the ministry archive shown in your instructions and write the response to the citizen now.", subject, description)

	answer, err := c.callMessages(ctx, apiMessageRequest{
		Model:     c.Model,
		MaxTokens: 1024,
		System:    system,
		Messages:  []apiMessage{{Role: "user", Content: userPrompt}},
	})
	if err != nil {
		return "", err
	}
	if strings.TrimSpace(answer) == "" {
		return "", fmt.Errorf("anthropic returned empty answer")
	}
	return answer, nil
}

// ----------------------------------------------------------------------------
// Structuring a fresh request for officer review
// ----------------------------------------------------------------------------

// ProcessRequestStructure asks Claude to produce a JSON analysis of a freshly
// filed request: classification, key questions, completeness score, etc.
// On any failure, a heuristic fallback structure is returned so the rest of
// the request-creation flow can continue.
func (c *Client) ProcessRequestStructure(ctx context.Context, subject, description, departmentID string) map[string]any {
	if !c.Configured() {
		log.Println("[ai] no API key — using fallback request structure")
		return fallbackStructure(subject, description)
	}

	prompt := fmt.Sprintf(`You are an AI assistant helping process Right to Information (RTI) requests in the Maldives.

Analyze the following RTI request and provide a structured analysis in JSON format.

CITIZEN REQUEST:
Subject: %s
Description: %s
Department: %s

Provide your analysis as a JSON object with these fields:

1. "request_type": Classify as "Data Request", "Policy Clarification", "Document Access", "Budget Information", "Procedure Inquiry", or "Other"
2. "key_questions": List 2-4 main questions the citizen is asking
3. "information_sought": List specific data, documents, or information items requested
4. "time_period": Extract any time period mentioned or null
5. "geographic_scope": Extract any geographic scope or null
6. "urgency_indicators": List any time-sensitive aspects (empty array if none)
7. "completeness_score": Rate 0.0 to 1.0 how complete and clear the request is
8. "missing_information": List what additional information would make this request clearer (empty array if complete)
9. "related_policies": List relevant Maldivian laws, policies, or RTI Act provisions (empty array if none obvious)
10. "estimated_complexity": "Simple", "Moderate", or "Complex"
11. "suggested_response_approach": Brief 2-3 sentence suggestion on how the officer should approach responding
12. "relevant_precedents": List any similar types of requests that might have been processed before (empty array if none)

Respond ONLY with the JSON object, no other text.`, subject, description, departmentID)

	// Use sonnet for the structuring task (matches the Python implementation).
	model := os.Getenv("ANTHROPIC_STRUCTURE_MODEL")
	if model == "" {
		model = "claude-3-5-sonnet-20241022"
	}
	raw, err := c.callMessages(ctx, apiMessageRequest{
		Model:     model,
		MaxTokens: 2000,
		Messages:  []apiMessage{{Role: "user", Content: prompt}},
	})
	if err != nil {
		log.Printf("[ai] structuring call failed: %v", err)
		return fallbackStructure(subject, description)
	}

	// Strip optional ```json fences before parsing.
	cleaned := strings.TrimSpace(raw)
	if strings.Contains(cleaned, "```json") {
		cleaned = strings.SplitN(cleaned, "```json", 2)[1]
		cleaned = strings.SplitN(cleaned, "```", 2)[0]
	} else if strings.HasPrefix(cleaned, "```") {
		cleaned = strings.TrimPrefix(cleaned, "```")
		if i := strings.Index(cleaned, "```"); i != -1 {
			cleaned = cleaned[:i]
		}
	}
	cleaned = strings.TrimSpace(cleaned)

	var parsed map[string]any
	if err := json.Unmarshal([]byte(cleaned), &parsed); err != nil {
		log.Printf("[ai] could not parse structured response: %v", err)
		return fallbackStructure(subject, description)
	}
	return parsed
}

func fallbackStructure(subject, description string) map[string]any {
	info := description
	if len(info) > 200 {
		info = info[:200] + "..."
	}
	return map[string]any{
		"request_type":                "Data Request",
		"key_questions":               []any{subject},
		"information_sought":          []any{info},
		"time_period":                 nil,
		"geographic_scope":            nil,
		"urgency_indicators":          []any{},
		"completeness_score":          0.6,
		"missing_information":         []any{"Request requires officer review to determine needed clarifications"},
		"related_policies":            []any{"Right to Information Act (Act No. 1/2014)"},
		"estimated_complexity":        "Moderate",
		"suggested_response_approach": "Review the request details and determine if all necessary information has been provided. Contact the citizen if clarification is needed.",
		"relevant_precedents":         []any{},
	}
}
