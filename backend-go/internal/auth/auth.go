// Package auth implements user signup/login, bcrypt password hashing, JWT
// issuance, and the chi middleware used to authenticate requests.
//
// The user store is intentionally kept in-memory (matching the original
// FastAPI implementation) — restarting the server clears all accounts apart
// from the default users seeded at startup.
package auth

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
)

// UserPublic is the safe-to-return shape of a user record (no password hash).
type UserPublic struct {
	Email          string `json:"email"`
	FullName       string `json:"full_name"`
	PresentAddress string `json:"present_address"`
	PhoneNumber    string `json:"phone_number"`
	IDCard         string `json:"id_card,omitempty"`
	IsAdmin        bool   `json:"is_admin"`
}

// AuthResponse is the body returned by signup and login.
type AuthResponse struct {
	AccessToken string     `json:"access_token"`
	TokenType   string     `json:"token_type"`
	User        UserPublic `json:"user"`
}

// SignupRequest is the JSON body accepted by POST /api/auth/signup.
type SignupRequest struct {
	Email          string `json:"email"`
	Password       string `json:"password"`
	FullName       string `json:"full_name"`
	PresentAddress string `json:"present_address"`
	PhoneNumber    string `json:"phone_number"`
	IDCard         string `json:"id_card"`
}

// LoginRequest is the JSON body accepted by POST /api/auth/login.
type LoginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type userRecord struct {
	Email          string
	FullName       string
	PresentAddress string
	PhoneNumber    string
	IDCard         string
	IsAdmin        bool
	PasswordHash   []byte
}

// Service holds the in-memory user store and JWT signing config.
type Service struct {
	mu          sync.RWMutex
	users       map[string]*userRecord
	jwtSecret   []byte
	jwtExpiry   time.Duration
	adminEmails map[string]struct{}
}

// New builds a Service. JWT_SECRET_KEY and ADMIN_EMAILS are pulled from env.
func New() *Service {
	secret := os.Getenv("JWT_SECRET_KEY")
	if secret == "" {
		log.Println("[auth] JWT_SECRET_KEY not set; using insecure dev fallback")
		secret = "dev-only-insecure-secret-do-not-use-in-production"
	}
	admins := map[string]struct{}{}
	for _, e := range strings.Split(os.Getenv("ADMIN_EMAILS"), ",") {
		e = strings.ToLower(strings.TrimSpace(e))
		if e != "" {
			admins[e] = struct{}{}
		}
	}
	return &Service{
		users:       map[string]*userRecord{},
		jwtSecret:   []byte(secret),
		jwtExpiry:   24 * time.Hour,
		adminEmails: admins,
	}
}

func normEmail(e string) string {
	return strings.ToLower(strings.TrimSpace(e))
}

func (s *Service) isAdminEmail(email string) bool {
	_, ok := s.adminEmails[normEmail(email)]
	return ok
}

func (s *Service) toPublic(r *userRecord) UserPublic {
	return UserPublic{
		Email:          r.Email,
		FullName:       r.FullName,
		PresentAddress: r.PresentAddress,
		PhoneNumber:    r.PhoneNumber,
		IDCard:         r.IDCard,
		IsAdmin:        r.IsAdmin,
	}
}

// Errors returned by the user-management primitives. The handler layer maps
// these to HTTP status codes.
var (
	ErrUserExists        = errors.New("user already exists")
	ErrInvalidCredential = errors.New("invalid email or password")
	ErrMissingField      = errors.New("required field missing")
	ErrInvalidToken      = errors.New("invalid token")
)

// CreateUser registers a new user; returns ErrUserExists if the email is
// already taken.
func (s *Service) CreateUser(req SignupRequest) (UserPublic, error) {
	email := normEmail(req.Email)
	if email == "" {
		return UserPublic{}, fmt.Errorf("%w: email", ErrMissingField)
	}
	fullName := strings.TrimSpace(req.FullName)
	address := strings.TrimSpace(req.PresentAddress)
	phone := strings.TrimSpace(req.PhoneNumber)
	if fullName == "" || address == "" || phone == "" {
		return UserPublic{}, fmt.Errorf("%w: name, address, and phone are required", ErrMissingField)
	}
	if len(req.Password) < 1 {
		return UserPublic{}, fmt.Errorf("%w: password", ErrMissingField)
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.users[email]; ok {
		return UserPublic{}, ErrUserExists
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
	if err != nil {
		return UserPublic{}, fmt.Errorf("hash password: %w", err)
	}
	idCard := strings.TrimSpace(req.IDCard)
	rec := &userRecord{
		Email:          email,
		FullName:       fullName,
		PresentAddress: address,
		PhoneNumber:    phone,
		IDCard:         idCard,
		IsAdmin:        s.isAdminEmail(email),
		PasswordHash:   hash,
	}
	s.users[email] = rec
	return s.toPublic(rec), nil
}

// Authenticate verifies a login attempt and returns the public user shape.
func (s *Service) Authenticate(email, password string) (UserPublic, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := normEmail(email)
	rec, ok := s.users[key]
	if !ok {
		// Run a dummy bcrypt verify to keep timing consistent.
		_ = bcrypt.CompareHashAndPassword([]byte("$2a$10$abcdefghijklmnopqrstuvwxyz012345"), []byte(password))
		return UserPublic{}, ErrInvalidCredential
	}
	if err := bcrypt.CompareHashAndPassword(rec.PasswordHash, []byte(password)); err != nil {
		return UserPublic{}, ErrInvalidCredential
	}
	// Retrofit admin flag in case ADMIN_EMAILS gained this email post-signup.
	if s.isAdminEmail(rec.Email) && !rec.IsAdmin {
		rec.IsAdmin = true
	}
	return s.toPublic(rec), nil
}

// CreateAccessToken signs and returns a 24-hour JWT for the user.
func (s *Service) CreateAccessToken(u UserPublic) (string, error) {
	now := time.Now()
	claims := jwt.MapClaims{
		"sub":      u.Email,
		"name":     u.FullName,
		"is_admin": u.IsAdmin,
		"iat":      now.Unix(),
		"exp":      now.Add(s.jwtExpiry).Unix(),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString(s.jwtSecret)
}

// VerifyToken parses and validates a bearer token, returning the live user.
func (s *Service) VerifyToken(raw string) (UserPublic, error) {
	tok, err := jwt.Parse(raw, func(t *jwt.Token) (any, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
		}
		return s.jwtSecret, nil
	})
	if err != nil || !tok.Valid {
		return UserPublic{}, ErrInvalidToken
	}
	claims, ok := tok.Claims.(jwt.MapClaims)
	if !ok {
		return UserPublic{}, ErrInvalidToken
	}
	email, _ := claims["sub"].(string)
	if email == "" {
		return UserPublic{}, ErrInvalidToken
	}
	s.mu.RLock()
	rec, ok := s.users[normEmail(email)]
	s.mu.RUnlock()
	if !ok {
		return UserPublic{}, ErrInvalidToken
	}
	return s.toPublic(rec), nil
}

// ctxKey is unexported to prevent collisions with other packages' context keys.
type ctxKey int

const (
	userCtxKey ctxKey = iota
)

// FromContext extracts the user attached by RequireAuth/RequireAdmin.
func FromContext(ctx context.Context) (UserPublic, bool) {
	u, ok := ctx.Value(userCtxKey).(UserPublic)
	return u, ok
}

func withUser(ctx context.Context, u UserPublic) context.Context {
	return context.WithValue(ctx, userCtxKey, u)
}

// RequireAuth is chi middleware: rejects requests without a valid bearer
// token, otherwise attaches the user to the request context.
func (s *Service) RequireAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hdr := r.Header.Get("Authorization")
		if !strings.HasPrefix(hdr, "Bearer ") {
			writeJSONError(w, http.StatusUnauthorized, "Could not validate credentials.")
			return
		}
		token := strings.TrimSpace(strings.TrimPrefix(hdr, "Bearer "))
		user, err := s.VerifyToken(token)
		if err != nil {
			writeJSONError(w, http.StatusUnauthorized, "Could not validate credentials.")
			return
		}
		next.ServeHTTP(w, r.WithContext(withUser(r.Context(), user)))
	})
}

// RequireAdmin extends RequireAuth with an admin-only check.
func (s *Service) RequireAdmin(next http.Handler) http.Handler {
	return s.RequireAuth(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		u, ok := FromContext(r.Context())
		if !ok || !u.IsAdmin {
			writeJSONError(w, http.StatusForbidden, "Administrator access required.")
			return
		}
		next.ServeHTTP(w, r)
	}))
}

func writeJSONError(w http.ResponseWriter, status int, detail string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"detail": detail})
}

// RandomSecret is a helper used by tests / scripts that want a fresh JWT key.
func RandomSecret() string {
	b := make([]byte, 32)
	_, _ = rand.Read(b)
	return base64.StdEncoding.EncodeToString(b)
}
