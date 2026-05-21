package graph

import (
	"regexp"
	"strings"
)

var tokenRe = regexp.MustCompile(`[A-Za-z][A-Za-z0-9]+`)

// stopWords mirrors the rag package's stop list so the two retrievers see
// the same vocabulary.
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

// tokenize lowercases, splits on word boundaries, drops short tokens and
// stopwords. The same threshold (≥ 4 chars) is used to keep graph nodes
// "notable" — matching the spirit of the original entity-extraction layer.
func tokenize(text string) []string {
	matches := tokenRe.FindAllString(strings.ToLower(text), -1)
	out := make([]string, 0, len(matches))
	for _, m := range matches {
		if len(m) < 4 {
			continue
		}
		if _, skip := stopWords[m]; skip {
			continue
		}
		out = append(out, m)
	}
	return out
}
