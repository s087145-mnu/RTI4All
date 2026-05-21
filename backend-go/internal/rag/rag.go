// Package rag implements a small in-process retrieval layer used to ground
// the AI's drafts in the ministry archive (past responded RTI requests +
// FAQs).
//
// The original Python implementation used sentence-transformers
// (all-MiniLM-L6-v2) for embeddings. Pulling 300 MB of PyTorch into a Go
// binary is impractical, so this Go port uses a deterministic TF-IDF +
// cosine-similarity retriever instead. The retrieval contract is identical:
// callers supply a query string and get back ranked payloads with a `_score`
// in [0, 1].
package rag

import (
	"fmt"
	"math"
	"regexp"
	"sort"
	"strings"
	"sync"

	"github.com/rti4all/backend-go/internal/models"
)

var tokenRe = regexp.MustCompile(`[A-Za-z][A-Za-z0-9]+`)

// stopWords are removed before tokenization to make scoring less noisy.
var stopWords = map[string]struct{}{
	"the": {}, "and": {}, "for": {}, "with": {}, "that": {}, "this": {},
	"from": {}, "are": {}, "was": {}, "were": {}, "have": {}, "has": {},
	"will": {}, "you": {}, "your": {}, "our": {}, "his": {}, "her": {},
	"its": {}, "their": {}, "what": {}, "which": {}, "who": {}, "when": {},
	"where": {}, "why": {}, "how": {}, "any": {}, "all": {}, "more": {},
	"please": {}, "kindly": {}, "would": {}, "could": {}, "should": {},
	"about": {}, "into": {}, "than": {}, "then": {}, "also": {}, "been": {},
	"being": {}, "such": {},
}

func tokenize(text string) []string {
	matches := tokenRe.FindAllString(strings.ToLower(text), -1)
	out := make([]string, 0, len(matches))
	for _, m := range matches {
		if len(m) < 3 {
			continue
		}
		if _, skip := stopWords[m]; skip {
			continue
		}
		out = append(out, m)
	}
	return out
}

type docVector struct {
	terms map[string]float64 // L2-normalized TF-IDF weights
}

// Index is a TF-IDF cosine-similarity store.
type Index struct {
	mu       sync.RWMutex
	ids      []string
	payloads []map[string]any
	vectors  []docVector
	idf      map[string]float64
	docFreq  map[string]int
	docCount int
}

// NewIndex builds an empty index.
func NewIndex() *Index {
	return &Index{idf: map[string]float64{}, docFreq: map[string]int{}}
}

// Len returns the number of indexed items.
func (i *Index) Len() int {
	i.mu.RLock()
	defer i.mu.RUnlock()
	return len(i.ids)
}

func (i *Index) recompute(rawDocs []map[string]int) {
	// Recompute IDF and per-doc TF-IDF vectors from raw term frequencies.
	i.docFreq = map[string]int{}
	for _, tf := range rawDocs {
		for term := range tf {
			i.docFreq[term]++
		}
	}
	i.idf = map[string]float64{}
	n := float64(len(rawDocs))
	for term, df := range i.docFreq {
		// Smoothed inverse document frequency.
		i.idf[term] = math.Log((n+1.0)/(float64(df)+1.0)) + 1.0
	}
	i.docCount = len(rawDocs)
	i.vectors = make([]docVector, len(rawDocs))
	for idx, tf := range rawDocs {
		i.vectors[idx] = i.buildVector(tf)
	}
}

func (i *Index) buildVector(tf map[string]int) docVector {
	v := docVector{terms: make(map[string]float64, len(tf))}
	var norm float64
	for term, count := range tf {
		w := float64(count) * i.idf[term]
		v.terms[term] = w
		norm += w * w
	}
	if norm > 0 {
		norm = math.Sqrt(norm)
		for term := range v.terms {
			v.terms[term] /= norm
		}
	}
	return v
}

// Item is the input form passed to BulkLoad / Upsert.
type Item struct {
	ID      string
	Text    string
	Payload map[string]any
}

// BulkLoad replaces the index contents with the provided items.
func (i *Index) BulkLoad(items []Item) {
	i.mu.Lock()
	defer i.mu.Unlock()

	i.ids = make([]string, 0, len(items))
	i.payloads = make([]map[string]any, 0, len(items))

	rawDocs := make([]map[string]int, 0, len(items))
	for _, it := range items {
		i.ids = append(i.ids, it.ID)
		i.payloads = append(i.payloads, it.Payload)
		tf := map[string]int{}
		for _, tok := range tokenize(it.Text) {
			tf[tok]++
		}
		rawDocs = append(rawDocs, tf)
	}
	i.recompute(rawDocs)
}

// Upsert adds or replaces a single item. It triggers a full IDF recompute
// because adding documents shifts the global term statistics; at the
// expected corpus size (hundreds of items) this is essentially free.
func (i *Index) Upsert(id, text string, payload map[string]any) {
	i.mu.Lock()
	defer i.mu.Unlock()

	tf := map[string]int{}
	for _, tok := range tokenize(text) {
		tf[tok]++
	}

	// Rebuild raw TF maps for the existing corpus so recompute can re-derive
	// IDF and re-vectorize everything with the new term distribution.
	rawDocs := make([]map[string]int, len(i.ids))
	for idx, v := range i.vectors {
		// We don't keep raw TFs around; reverse-engineer counts from the
		// L2-normalized weight by dividing through IDF. This is only used
		// for IDF/df recomputation, which only needs presence/absence of
		// terms and not exact counts, so we can recover well enough by
		// re-tokenising the underlying payload text.
		_ = v
		raw := map[string]int{}
		txt := payloadText(i.payloads[idx])
		for _, tok := range tokenize(txt) {
			raw[tok]++
		}
		rawDocs[idx] = raw
	}

	replaced := false
	for idx, existing := range i.ids {
		if existing == id {
			i.payloads[idx] = payload
			rawDocs[idx] = tf
			replaced = true
			break
		}
	}
	if !replaced {
		i.ids = append(i.ids, id)
		i.payloads = append(i.payloads, payload)
		rawDocs = append(rawDocs, tf)
	}

	i.recompute(rawDocs)
}

// Hit is a single retrieval result. The original payload fields are returned
// alongside a score in [0, 1].
type Hit struct {
	Payload map[string]any
	Score   float64
}

// Retrieve returns up to k payloads ranked by cosine similarity to the query.
func (i *Index) Retrieve(query string, k int) []Hit {
	i.mu.RLock()
	defer i.mu.RUnlock()

	if len(i.ids) == 0 || strings.TrimSpace(query) == "" {
		return nil
	}
	qTF := map[string]int{}
	for _, tok := range tokenize(query) {
		qTF[tok]++
	}
	qVec := i.buildVector(qTF)
	if len(qVec.terms) == 0 {
		return nil
	}
	type scored struct {
		idx   int
		score float64
	}
	scores := make([]scored, 0, len(i.vectors))
	for idx, v := range i.vectors {
		s := cosine(qVec, v)
		if s > 0 {
			scores = append(scores, scored{idx, s})
		}
	}
	sort.Slice(scores, func(a, b int) bool { return scores[a].score > scores[b].score })
	if k > len(scores) {
		k = len(scores)
	}
	out := make([]Hit, 0, k)
	for _, s := range scores[:k] {
		payload := make(map[string]any, len(i.payloads[s.idx])+1)
		for k, v := range i.payloads[s.idx] {
			payload[k] = v
		}
		out = append(out, Hit{Payload: payload, Score: s.score})
	}
	return out
}

func cosine(a, b docVector) float64 {
	// Both vectors are L2-normalised so cosine == dot product.
	if len(a.terms) > len(b.terms) {
		a, b = b, a
	}
	var sum float64
	for term, wa := range a.terms {
		if wb, ok := b.terms[term]; ok {
			sum += wa * wb
		}
	}
	return sum
}

func payloadText(p map[string]any) string {
	switch p["kind"] {
	case "request":
		return strings.Join([]string{
			asString(p["subject"]),
			asString(p["description"]),
			asString(p["response"]),
		}, "\n")
	case "faq":
		return asString(p["question"]) + "\n" + asString(p["answer"])
	}
	return ""
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

// PopulateFromDB seeds the index from the on-disk store. Only past
// *responded* RTI requests and FAQs are indexed — pending requests aren't
// useful as precedent.
func PopulateFromDB(idx *Index, db *models.DB) {
	items := make([]Item, 0, len(db.Requests)+len(db.FAQs))
	for _, r := range db.Requests {
		if r.Status != "Responded" || r.Response == "" {
			continue
		}
		text := strings.Join([]string{r.Subject, r.Description, r.Response}, "\n")
		items = append(items, Item{
			ID:   "req:" + r.ID,
			Text: text,
			Payload: map[string]any{
				"kind":        "request",
				"id":          r.ID,
				"subject":     r.Subject,
				"description": r.Description,
				"response":    r.Response,
				"status":      r.Status,
				"date_filed":  r.DateFiled,
			},
		})
	}
	for _, f := range db.FAQs {
		items = append(items, Item{
			ID:   "faq:" + f.ID,
			Text: f.Question + "\n" + f.Answer,
			Payload: map[string]any{
				"kind":     "faq",
				"id":       f.ID,
				"question": f.Question,
				"answer":   f.Answer,
			},
		})
	}
	idx.BulkLoad(items)
}

// IndexResponded adds (or refreshes) one responded request after officer
// approval — closing the feedback loop so future drafts can cite it.
func IndexResponded(idx *Index, r *models.RTIRequest) {
	if r.Status != "Responded" || r.Response == "" {
		return
	}
	text := strings.Join([]string{r.Subject, r.Description, r.Response}, "\n")
	idx.Upsert("req:"+r.ID, text, map[string]any{
		"kind":        "request",
		"id":          r.ID,
		"subject":     r.Subject,
		"description": r.Description,
		"response":    r.Response,
		"status":      r.Status,
		"date_filed":  r.DateFiled,
	})
}

// FormatForPrompt renders retrieval hits as a citation-ready block for the
// AI system prompt.
func FormatForPrompt(hits []Hit) string {
	if len(hits) == 0 {
		return "(no related ministry records found in the local archive)"
	}
	var b strings.Builder
	for i, h := range hits {
		p := h.Payload
		switch p["kind"] {
		case "request":
			fmt.Fprintf(&b, "[%d] Past responded RTI · %s (filed %s)\n    Subject: %s\n    Description: %s\n    Official response: %s",
				i+1, asString(p["id"]), asString(p["date_filed"]),
				asString(p["subject"]), asString(p["description"]), asString(p["response"]))
		case "faq":
			fmt.Fprintf(&b, "[%d] FAQ · %s\n    Q: %s\n    A: %s",
				i+1, asString(p["id"]), asString(p["question"]), asString(p["answer"]))
		}
		if i < len(hits)-1 {
			b.WriteString("\n\n")
		}
	}
	return b.String()
}
