// Command rti4all is the Go entrypoint for the RTI4All backend.
//
// It loads the seed data, builds the retrieval indexes, seeds the default
// users, installs CORS + the chi routes, and starts an HTTP server on
// :8000 (configurable via PORT).
package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/go-chi/cors"
	"github.com/rti4all/backend-go/internal/ai"
	"github.com/rti4all/backend-go/internal/auth"
	"github.com/rti4all/backend-go/internal/cache"
	"github.com/rti4all/backend-go/internal/graph"
	"github.com/rti4all/backend-go/internal/handlers"
	"github.com/rti4all/backend-go/internal/models"
	"github.com/rti4all/backend-go/internal/persistence"
	"github.com/rti4all/backend-go/internal/rag"
)

func main() {
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)

	dataFile := os.Getenv("DATA_FILE")
	if dataFile == "" {
		dataFile = filepath.Join("data", "sample_data.json")
	}
	port := os.Getenv("PORT")
	if port == "" {
		port = "8000"
	}

	// ----- Persistence ------------------------------------------------------
	maxBackups := 10
	if v, err := strconv.Atoi(os.Getenv("MAX_BACKUPS")); err == nil && v > 0 {
		maxBackups = v
	}
	enablePersistence := true
	switch strings.ToLower(os.Getenv("ENABLE_DATA_PERSISTENCE")) {
	case "false", "0", "no":
		enablePersistence = false
	}

	var (
		store *persistence.Store
		db    *models.DB
		err   error
	)
	if enablePersistence {
		store, err = persistence.NewStore(dataFile, true, maxBackups)
		if err != nil {
			log.Fatalf("[startup] init persistence: %v", err)
		}
		db, err = store.Load()
	} else {
		// Read-only mode: still need an in-memory copy of the seed data.
		ro, e := persistence.NewStore(dataFile, false, 0)
		if e != nil {
			log.Fatalf("[startup] init read-only store: %v", e)
		}
		db, err = ro.Load()
	}
	if err != nil {
		log.Fatalf("[startup] load data: %v", err)
	}

	// ----- Services ---------------------------------------------------------
	authSvc := auth.New()
	aiClient := ai.New()
	queryCache := cache.New()
	ragIdx := rag.NewIndex()
	graphState := graph.NewState()

	rag.PopulateFromDB(ragIdx, db)
	graphState.BuildFromDB(db)

	// Seed default users so the demo accounts referenced in docs work out
	// of the box on a fresh boot.
	seedDefaultUsers(authSvc)

	server := &handlers.Server{
		DB:        db,
		Auth:      authSvc,
		AI:        aiClient,
		Cache:     queryCache,
		RAG:       ragIdx,
		Graph:     graphState,
		Persistor: store,
	}

	// ----- HTTP -------------------------------------------------------------
	mux := server.Routes()

	corsHandler := cors.Handler(cors.Options{
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"*"},
		AllowCredentials: false,
		MaxAge:           300,
	})

	httpSrv := &http.Server{
		Addr:              ":" + port,
		Handler:           corsHandler(loggingMiddleware(mux)),
		ReadHeaderTimeout: 10 * time.Second,
	}

	log.Printf("[startup] ✓ RTI4All backend (Go) ready")
	log.Printf("[startup]   requests=%d departments=%d faqs=%d",
		len(db.Requests), len(db.Departments), len(db.FAQs))
	log.Printf("[startup]   RAG items=%d  graph docs=%d  persistence=%v  ai=%v",
		ragIdx.Len(), graphState.Len(), store != nil, aiClient.Configured())
	log.Printf("[startup]   listening on :%s", port)

	// Run the server in a goroutine so we can wait on signals in main.
	errCh := make(chan error, 1)
	go func() {
		if err := httpSrv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)

	select {
	case err := <-errCh:
		log.Fatalf("[server] %v", err)
	case sig := <-stop:
		log.Printf("[server] received %s, shutting down", sig)
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := httpSrv.Shutdown(ctx); err != nil {
			log.Printf("[server] graceful shutdown: %v", err)
		}
	}
}

// seedDefaultUsers creates the demo officer + citizen accounts on first boot.
// If they already exist (e.g. after a hot reload) the errors are swallowed.
func seedDefaultUsers(svc *auth.Service) {
	defaults := []auth.SignupRequest{
		{
			Email:          "officer@gov.mv",
			Password:       "super-secret-pass",
			FullName:       "Officer Hassan",
			PresentAddress: "Ministry HQ, Male'",
			PhoneNumber:    "+960 3001000",
		},
		{
			Email:          "citizen@example.mv",
			Password:       "another-pass",
			FullName:       "Aishath Hassan",
			PresentAddress: "H. Sunset, Hithadhoo, Addu City",
			PhoneNumber:    "+960 7777777",
			IDCard:         "A099887",
		},
	}
	for _, d := range defaults {
		if _, err := svc.CreateUser(d); err != nil {
			if !errors.Is(err, auth.ErrUserExists) {
				log.Printf("[startup] seed user %s: %v", d.Email, err)
			}
			continue
		}
		log.Printf("[startup] seeded default user %s", d.Email)
	}
}

// loggingMiddleware writes one log line per request for visibility.
func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rw := &statusRecorder{ResponseWriter: w, status: 200}
		next.ServeHTTP(rw, r)
		log.Printf("%s %s -> %d (%s)", r.Method, r.URL.Path, rw.status, time.Since(start))
	})
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (s *statusRecorder) WriteHeader(code int) {
	s.status = code
	s.ResponseWriter.WriteHeader(code)
}
