import { Container, LinkButton } from "@/components/ui";

export function NotFoundPage() {
  return (
    <Container size="sm" className="text-center">
      <div className="font-mono text-xs uppercase tracking-widest text-ink-400">
        404
      </div>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink-900">
        Page not found
      </h1>
      <p className="mx-auto mt-2 max-w-sm text-sm text-ink-500">
        The page you're looking for doesn't exist or has moved.
      </p>
      <div className="mt-6 flex justify-center">
        <LinkButton to="/" variant="primary">
          Back to home
        </LinkButton>
      </div>
    </Container>
  );
}
