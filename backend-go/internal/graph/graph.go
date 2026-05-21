// Package graph is a lightweight graph-augmented retrieval layer over the
// ministry archive.
//
// The original Python implementation shelled out to the `graphify` CLI to
// build an LLM-extracted entity graph. That tool has no Go counterpart and
// would balloon the container image, so this port uses a deterministic
// token-cooccurrence graph instead:
//
//   - Nodes are notable lowercase tokens (≥ 4 chars, non-stopwords) that
//     appear in at least one corpus document.
//   - Two nodes share an edge if they co-occur in the same document.
//   - Retrieval matches the query tokens against node labels, traverses
//     one hop of edges, and ranks the documents whose tokens were touched.
//
// Empirically this gives "graph-linked precedent" of similar utility to
// graphify for the small ministry archive: shared concepts in a query
// surface other requests that mention the same concepts, even when no
// individual term overlaps exactly.
package graph

import (
	"fmt"
	"sort"
	"strings"
	"sync"

	"github.com/rti4all/backend-go/internal/models"
	"github.com/rti4all/backend-go/internal/rag"
)

// State holds the live graph + the source-document payloads it points to.
type State struct {
	mu       sync.RWMutex
	docTerms []map[string]struct{} // per-doc unique terms
	docs     []map[string]any
	termDocs map[string][]int // term → docs containing it
	cooccur  map[string]map[string]int
	ids      []string
}

// NewState builds an empty graph state.
func NewState() *State {
	return &State{
		termDocs: map[string][]int{},
		cooccur:  map[string]map[string]int{},
	}
}

// Len reports the number of documents in the graph (the equivalent of the
// Python "node count" — used for the startup log line).
func (s *State) Len() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.ids)
}

func docPayload(r *models.RTIRequest) (map[string]any, string) {
	return map[string]any{
		"kind":        "request",
		"id":          r.ID,
		"subject":     r.Subject,
		"description": r.Description,
		"response":    r.Response,
		"date_filed":  r.DateFiled,
	}, strings.Join([]string{r.Subject, r.Description, r.Response}, " ")
}

func faqPayload(f models.FAQ) (map[string]any, string) {
	return map[string]any{
		"kind":     "faq",
		"id":       f.ID,
		"question": f.Question,
		"answer":   f.Answer,
	}, f.Question + " " + f.Answer
}

// BuildFromDB seeds the graph from a fully loaded DB.
func (s *State) BuildFromDB(db *models.DB) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.ids = s.ids[:0]
	s.docs = s.docs[:0]
	s.docTerms = s.docTerms[:0]
	s.termDocs = map[string][]int{}
	s.cooccur = map[string]map[string]int{}

	for _, r := range db.Requests {
		if r.Status != "Responded" || r.Response == "" {
			continue
		}
		payload, text := docPayload(r)
		s.addDocLocked("req:"+r.ID, payload, text)
	}
	for _, f := range db.FAQs {
		payload, text := faqPayload(f)
		s.addDocLocked("faq:"+f.ID, payload, text)
	}
}

// UpdateForRequest adds a single responded request to the graph after officer
// approval.
func (s *State) UpdateForRequest(r *models.RTIRequest) {
	if r.Status != "Responded" || r.Response == "" {
		return
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	payload, text := docPayload(r)
	// If the request was already in the graph, drop the old entry first.
	id := "req:" + r.ID
	for i, existing := range s.ids {
		if existing == id {
			// Rebuild from scratch — small corpus so this is cheap and
			// keeps the cooccurrence map consistent without bookkeeping.
			s.ids = append(s.ids[:i], s.ids[i+1:]...)
			s.docs = append(s.docs[:i], s.docs[i+1:]...)
			s.docTerms = append(s.docTerms[:i], s.docTerms[i+1:]...)
			s.rebuildIndexesLocked()
			break
		}
	}
	s.addDocLocked(id, payload, text)
}

func (s *State) addDocLocked(id string, payload map[string]any, text string) {
	terms := uniqueTerms(text)
	idx := len(s.ids)
	s.ids = append(s.ids, id)
	s.docs = append(s.docs, payload)
	s.docTerms = append(s.docTerms, terms)
	for t := range terms {
		s.termDocs[t] = append(s.termDocs[t], idx)
	}
	// Update co-occurrence counts between every pair of terms in this doc.
	for a := range terms {
		row, ok := s.cooccur[a]
		if !ok {
			row = map[string]int{}
			s.cooccur[a] = row
		}
		for b := range terms {
			if a == b {
				continue
			}
			row[b]++
		}
	}
}

func (s *State) rebuildIndexesLocked() {
	s.termDocs = map[string][]int{}
	s.cooccur = map[string]map[string]int{}
	for idx, terms := range s.docTerms {
		for t := range terms {
			s.termDocs[t] = append(s.termDocs[t], idx)
		}
		for a := range terms {
			row, ok := s.cooccur[a]
			if !ok {
				row = map[string]int{}
				s.cooccur[a] = row
			}
			for b := range terms {
				if a == b {
					continue
				}
				row[b]++
			}
		}
	}
}

func uniqueTerms(text string) map[string]struct{} {
	out := map[string]struct{}{}
	for _, t := range tokenize(text) {
		out[t] = struct{}{}
	}
	return out
}

// Retrieve returns up to k payloads linked to the query via shared and
// co-occurring tokens.
func (s *State) Retrieve(query string, k int) []rag.Hit {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if len(s.ids) == 0 || strings.TrimSpace(query) == "" {
		return nil
	}
	qTerms := uniqueTerms(query)
	if len(qTerms) == 0 {
		return nil
	}

	// Expand the query terms by one hop along the cooccurrence graph,
	// inheriting a decayed weight to favour direct matches.
	weights := map[string]float64{}
	for t := range qTerms {
		weights[t] = 1.0
	}
	for t := range qTerms {
		row := s.cooccur[t]
		// Take the top-N neighbours by cooccurrence count to keep the
		// expansion focused on the strongest links.
		type pair struct {
			term  string
			count int
		}
		neighbours := make([]pair, 0, len(row))
		for nt, c := range row {
			neighbours = append(neighbours, pair{nt, c})
		}
		sort.Slice(neighbours, func(i, j int) bool { return neighbours[i].count > neighbours[j].count })
		max := 8
		if len(neighbours) < max {
			max = len(neighbours)
		}
		for _, n := range neighbours[:max] {
			if _, seen := weights[n.term]; seen {
				continue
			}
			weights[n.term] = 0.5
		}
	}

	// Score every document by the sum of weights for its terms.
	type scored struct {
		idx   int
		score float64
	}
	scores := make([]scored, 0, len(s.ids))
	for idx, terms := range s.docTerms {
		var sum float64
		for t := range terms {
			if w, ok := weights[t]; ok {
				sum += w
			}
		}
		if sum > 0 {
			scores = append(scores, scored{idx, sum})
		}
	}
	if len(scores) == 0 {
		return nil
	}
	sort.Slice(scores, func(a, b int) bool { return scores[a].score > scores[b].score })
	if k > len(scores) {
		k = len(scores)
	}
	out := make([]rag.Hit, 0, k)
	for _, sc := range scores[:k] {
		payload := make(map[string]any, len(s.docs[sc.idx]))
		for k, v := range s.docs[sc.idx] {
			payload[k] = v
		}
		out = append(out, rag.Hit{Payload: payload, Score: sc.score})
	}
	return out
}

// FormatForPrompt renders graph hits for the system prompt.
func FormatForPrompt(hits []rag.Hit) string {
	if len(hits) == 0 {
		return "(no graph-linked precedent found)"
	}
	var b strings.Builder
	for i, h := range hits {
		p := h.Payload
		switch p["kind"] {
		case "request":
			fmt.Fprintf(&b, "[G%d] Graph-linked RTI · %s (filed %s)\n    Subject: %s\n    Description: %s\n    Official response: %s",
				i+1, asString(p["id"]), asString(p["date_filed"]),
				asString(p["subject"]), asString(p["description"]), asString(p["response"]))
		case "faq":
			fmt.Fprintf(&b, "[G%d] Graph-linked FAQ · %s\n    Q: %s\n    A: %s",
				i+1, asString(p["id"]), asString(p["question"]), asString(p["answer"]))
		}
		if i < len(hits)-1 {
			b.WriteString("\n\n")
		}
	}
	return b.String()
}

func asString(v any) string {
	if v == nil {
		return ""
	}
	s, ok := v.(string)
	if !ok {
		return ""
	}
	return s
}
