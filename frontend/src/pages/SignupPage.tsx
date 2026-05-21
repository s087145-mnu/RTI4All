import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  Button,
  Card,
  CardBody,
  Container,
  ErrorBanner,
  Field,
  Input,
  Textarea,
} from "@/components/ui";

interface FormState {
  full_name: string;
  email: string;
  phone_number: string;
  present_address: string;
  id_card: string;
  password: string;
}

export function SignupPage() {
  const { signup, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      navigate(user.is_admin ? "/admin" : "/requests/new", { replace: true });
    }
  }, [user, navigate]);

  const [form, setForm] = useState<FormState>({
    full_name: "",
    email: "",
    phone_number: "",
    present_address: "",
    id_card: "",
    password: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onChange = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const payload = { ...form, id_card: form.id_card.trim() || undefined };
      const newUser = await signup(payload);
      navigate(newUser.is_admin ? "/admin" : "/requests/new", { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  return (
    <Container size="sm" className="max-w-lg">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
          Create your account
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          You'll be able to file and track RTI requests once registered.
        </p>
      </div>

      <Card className="mt-8">
        <CardBody>
          {error ? <div className="mb-4"><ErrorBanner message={error} /></div> : null}
          <form onSubmit={onSubmit} className="space-y-4">
            <Field label="Full name" required>
              <Input
                required
                placeholder="e.g. Aishath Hassan"
                value={form.full_name}
                onChange={(e) => onChange("full_name", e.target.value)}
              />
            </Field>
            <Field label="Email" required>
              <Input
                type="email"
                required
                placeholder="you@example.mv"
                value={form.email}
                onChange={(e) => onChange("email", e.target.value)}
              />
            </Field>
            <Field label="Phone number" required>
              <Input
                type="tel"
                required
                placeholder="+960 7771234"
                value={form.phone_number}
                onChange={(e) => onChange("phone_number", e.target.value)}
              />
            </Field>
            <Field label="Present address" required>
              <Textarea
                required
                rows={2}
                placeholder="e.g. M. Anbara, Majeedhee Magu, Male'"
                value={form.present_address}
                onChange={(e) => onChange("present_address", e.target.value)}
              />
            </Field>
            <Field label="National ID" hint="Optional">
              <Input
                placeholder="A123456"
                value={form.id_card}
                onChange={(e) => onChange("id_card", e.target.value)}
              />
            </Field>
            <Field label="Password" required hint="Minimum 8 characters">
              <Input
                type="password"
                required
                minLength={8}
                value={form.password}
                onChange={(e) => onChange("password", e.target.value)}
              />
            </Field>
            <Button
              type="submit"
              variant="primary"
              loading={submitting}
              className="w-full"
            >
              {submitting ? "Creating account…" : "Create account"}
            </Button>
          </form>
        </CardBody>
      </Card>

      <p className="mt-6 text-center text-sm text-ink-500">
        Already registered?{" "}
        <Link
          to="/login"
          className="font-medium text-accent-600 hover:text-accent-700"
        >
          Sign in
        </Link>
      </p>
    </Container>
  );
}
