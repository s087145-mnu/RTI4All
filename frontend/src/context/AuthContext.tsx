import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, UNAUTHORIZED_EVENT } from "@/api/client";
import type { LoginPayload, SignupPayload, UserPublic } from "@/types/api";

const STORAGE_KEY = "rti4all-auth";

interface AuthState {
  user: UserPublic | null;
  token: string | null;
}

interface AuthContextValue extends AuthState {
  login: (payload: LoginPayload) => Promise<UserPublic>;
  signup: (payload: SignupPayload) => Promise<UserPublic>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function loadStoredAuth(): AuthState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { user: null, token: null };
    return JSON.parse(raw) as AuthState;
  } catch {
    return { user: null, token: null };
  }
}

/** Provider that owns the auth token + user, persisted to localStorage. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => loadStoredAuth());

  const persist = useCallback((next: AuthState) => {
    setState(next);
    if (next.token) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const login = useCallback(
    async (payload: LoginPayload) => {
      const data = await api.login(payload);
      persist({ user: data.user, token: data.access_token });
      return data.user;
    },
    [persist],
  );

  const signup = useCallback(
    async (payload: SignupPayload) => {
      const data = await api.signup(payload);
      persist({ user: data.user, token: data.access_token });
      return data.user;
    },
    [persist],
  );

  const logout = useCallback(() => persist({ user: null, token: null }), [persist]);

  // If the API ever returns 401, drop the stale token so the router can
  // bounce the user to /login. The event is emitted by the api client.
  useEffect(() => {
    const handler = () => persist({ user: null, token: null });
    window.addEventListener(UNAUTHORIZED_EVENT, handler);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handler);
  }, [persist]);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, signup, logout }),
    [state, login, signup, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth() must be used inside <AuthProvider>");
  return ctx;
}
