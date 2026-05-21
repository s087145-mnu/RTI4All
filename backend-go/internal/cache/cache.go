// Package cache is a tiny in-memory query cache for AI answers, keyed on
// (department_id, normalized text). Mirrors backend/cache.py.
package cache

import (
	"regexp"
	"strings"
	"sync"
)

var (
	punctRe = regexp.MustCompile(`[[:punct:]]+`)
	wsRe    = regexp.MustCompile(`\s+`)
)

func normalize(text string) string {
	text = strings.ToLower(text)
	text = punctRe.ReplaceAllString(text, " ")
	text = wsRe.ReplaceAllString(text, " ")
	return strings.TrimSpace(text)
}

// Key is a (department_id, normalized-text) compound key.
type Key struct {
	Dept string
	Norm string
}

// MakeKey produces the cache key for a request.
func MakeKey(deptID, subject, description string) Key {
	return Key{Dept: deptID, Norm: normalize(subject + " " + description)}
}

// Cache is a goroutine-safe in-memory map.
type Cache struct {
	mu    sync.RWMutex
	store map[Key]string
}

// New constructs an empty cache.
func New() *Cache {
	return &Cache{store: map[Key]string{}}
}

// Get returns the cached answer, if any.
func (c *Cache) Get(k Key) (string, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	v, ok := c.store[k]
	return v, ok
}

// Put stores an answer for later retrieval.
func (c *Cache) Put(k Key, v string) {
	c.mu.Lock()
	c.store[k] = v
	c.mu.Unlock()
}

// Len reports the number of cached items (test helper).
func (c *Cache) Len() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return len(c.store)
}
