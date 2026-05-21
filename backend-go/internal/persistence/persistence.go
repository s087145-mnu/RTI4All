// Package persistence handles loading and saving the JSON-backed application
// state with atomic writes and timestamped backups. It mirrors the behaviour
// of backend/persistence.py from the original Python implementation.
package persistence

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/rti4all/backend-go/internal/models"
)

// Store is the JSON-file-backed data store.
type Store struct {
	DataFile   string
	BackupDir  string
	AutoBackup bool
	MaxBackups int
}

// NewStore builds a Store rooted at the given data file. Backups land in a
// sibling `backups` directory by default.
func NewStore(dataFile string, autoBackup bool, maxBackups int) (*Store, error) {
	s := &Store{
		DataFile:   dataFile,
		BackupDir:  filepath.Join(filepath.Dir(dataFile), "backups"),
		AutoBackup: autoBackup,
		MaxBackups: maxBackups,
	}
	if err := os.MkdirAll(filepath.Dir(s.DataFile), 0o755); err != nil {
		return nil, fmt.Errorf("create data dir: %w", err)
	}
	if s.AutoBackup {
		if err := os.MkdirAll(s.BackupDir, 0o755); err != nil {
			return nil, fmt.Errorf("create backup dir: %w", err)
		}
	}
	return s, nil
}

// Load reads the data file. On JSON decode failure it attempts to recover
// from the most recent backup.
func (s *Store) Load() (*models.DB, error) {
	f, err := os.Open(s.DataFile)
	if err != nil {
		return nil, fmt.Errorf("open data file: %w", err)
	}
	defer f.Close()

	raw, err := io.ReadAll(f)
	if err != nil {
		return nil, fmt.Errorf("read data file: %w", err)
	}

	db := &models.DB{}
	if err := json.Unmarshal(raw, db); err != nil {
		log.Printf("[persistence] decode error on %s: %v — trying backup", s.DataFile, err)
		if recovered := s.tryRecover(); recovered != nil {
			return recovered, nil
		}
		return nil, fmt.Errorf("decode data file: %w", err)
	}

	// Normalise nil slices so downstream code can append safely.
	for _, r := range db.Requests {
		if r.ClarificationHistory == nil {
			r.ClarificationHistory = []map[string]any{}
		}
		if r.CitizenUpdates == nil {
			r.CitizenUpdates = []map[string]any{}
		}
	}
	if db.Requests == nil {
		db.Requests = []*models.RTIRequest{}
	}
	if db.Departments == nil {
		db.Departments = []models.Department{}
	}
	if db.FAQs == nil {
		db.FAQs = []models.FAQ{}
	}
	return db, nil
}

// Save writes the data file atomically (write tmp → rename) after creating
// an optional timestamped backup.
func (s *Store) Save(db *models.DB) error {
	if s.AutoBackup {
		if err := s.backup(); err != nil {
			log.Printf("[persistence] backup failed (continuing): %v", err)
		}
	}
	tmp := s.DataFile + ".tmp"
	f, err := os.Create(tmp)
	if err != nil {
		return fmt.Errorf("create tmp: %w", err)
	}
	enc := json.NewEncoder(f)
	enc.SetIndent("", "  ")
	enc.SetEscapeHTML(false)
	if err := enc.Encode(db); err != nil {
		_ = f.Close()
		_ = os.Remove(tmp)
		return fmt.Errorf("encode: %w", err)
	}
	if err := f.Close(); err != nil {
		_ = os.Remove(tmp)
		return fmt.Errorf("close tmp: %w", err)
	}
	if err := os.Rename(tmp, s.DataFile); err != nil {
		_ = os.Remove(tmp)
		return fmt.Errorf("rename: %w", err)
	}
	return nil
}

func (s *Store) backup() error {
	info, err := os.Stat(s.DataFile)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		return err
	}
	if info.Size() == 0 {
		return nil
	}
	ts := time.Now().Format("20060102_150405")
	dst := filepath.Join(s.BackupDir, fmt.Sprintf("sample_data_%s.json", ts))
	if err := copyFile(s.DataFile, dst); err != nil {
		return err
	}
	s.cleanupOldBackups()
	return nil
}

func (s *Store) cleanupOldBackups() {
	entries, err := os.ReadDir(s.BackupDir)
	if err != nil {
		return
	}
	type item struct {
		path string
		mod  time.Time
	}
	var items []item
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		if !strings.HasPrefix(e.Name(), "sample_data_") || !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		items = append(items, item{filepath.Join(s.BackupDir, e.Name()), info.ModTime()})
	}
	sort.Slice(items, func(i, j int) bool { return items[i].mod.After(items[j].mod) })
	for i := s.MaxBackups; i < len(items); i++ {
		_ = os.Remove(items[i].path)
	}
}

func (s *Store) tryRecover() *models.DB {
	entries, err := os.ReadDir(s.BackupDir)
	if err != nil {
		return nil
	}
	type item struct {
		path string
		mod  time.Time
	}
	var items []item
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		items = append(items, item{filepath.Join(s.BackupDir, e.Name()), info.ModTime()})
	}
	sort.Slice(items, func(i, j int) bool { return items[i].mod.After(items[j].mod) })
	for _, it := range items {
		raw, err := os.ReadFile(it.path)
		if err != nil {
			continue
		}
		db := &models.DB{}
		if err := json.Unmarshal(raw, db); err == nil {
			log.Printf("[persistence] recovered from backup %s", it.path)
			return db
		}
	}
	return nil
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, in); err != nil {
		out.Close()
		return err
	}
	return out.Close()
}
