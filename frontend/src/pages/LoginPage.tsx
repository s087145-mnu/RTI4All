import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  Button,
  Card,
  CardBody,
  Container,
  ErrorBanner,
  Field,
  Input,
} from "@/components/ui";

interface LocationState {
  from?: string;
}

export function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as LocationState | null)?.from;
  const defaultRedirect = user?.is_admin ? "/admin" : "/requests/new";
  const redirectTo = from ?? defaultRedirect;

  useEffect(() => {
    if (user) {
      navigate(user.is_admin ? "/admin" : redirectTo, { replace: true });
    }
  }, [user, navigate, redirectTo]);

  const [form, setForm] = useState({ email: "", password: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const loggedIn = await login(form);
      navigate(loggedIn.is_admin ? "/admin" : redirectTo, { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  return (
    <Container size="sm" className="max-w-md">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
          Sign in to RTI4All
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          Access your filed requests and the officer dashboard.
        </p>
      </div>

      <Card className="mt-8">
        <CardBody>
          {error ? <div className="mb-4"><ErrorBanner message={error} /></div> : null}
          <form onSubmit={onSubmit} className="space-y-4">
            <Field label="Email" required htmlFor="email">
              <Input
                id="email"
                name="email"
                type="email"
                required
                autoFocus
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@example.mv"
              />
            </Field>
            <Field label="Password" required htmlFor="password">
              <Input
                id="password"
                name="password"
                type="password"
                required
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="Your password"
              />
            </Field>
            <Button
              type="submit"
              variant="primary"
              loading={submitting}
              className="w-full"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardBody>
      </Card>

      <p className="mt-6 text-center text-sm text-ink-500">
        Don't have an account?{" "}
        <Link
          to="/signup"
          className="font-medium text-accent-600 hover:text-accent-700"
        >
          Create one
        </Link>
      </p>
    </Container>
  );
}
