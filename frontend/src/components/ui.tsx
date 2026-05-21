// Tiny in-house UI kit. We deliberately don't pull in shadcn / radix —
// the surface area we need is small and the design language is restrained:
// neutral surfaces, subtle borders, blue used sparingly.

import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { Link, type LinkProps } from "react-router-dom";
import { cn } from "@/lib/cn";
import type { RequestStatus } from "@/types/api";

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

export function Card({
  children,
  className,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article";
}) {
  return (
    <Tag
      className={cn(
        "rounded-xl border border-ink-200 bg-white shadow-card",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

export function CardHeader({
  title,
  description,
  action,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-ink-100 px-6 py-4">
      <div>
        <h2 className="text-base font-semibold text-ink-900">{title}</h2>
        {description ? (
          <p className="mt-1 text-sm text-ink-500">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function CardBody({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("px-6 py-5", className)}>{children}</div>;
}

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    "bg-ink-900 text-white hover:bg-ink-800 active:bg-ink-950 disabled:bg-ink-400",
  secondary:
    "bg-white text-ink-800 border border-ink-200 hover:bg-ink-50 hover:border-ink-300 disabled:text-ink-400",
  ghost:
    "bg-transparent text-ink-700 hover:bg-ink-100 hover:text-ink-900 disabled:text-ink-400",
  danger:
    "bg-red-600 text-white hover:bg-red-700 active:bg-red-800 disabled:bg-red-300",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-9 px-4 text-sm",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leftIcon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "secondary",
    size = "md",
    loading = false,
    className,
    children,
    leftIcon,
    disabled,
    type = "button",
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
        "disabled:cursor-not-allowed",
        buttonVariants[variant],
        buttonSizes[size],
        className,
      )}
      {...rest}
    >
      {loading ? <span className="spinner h-3 w-3" /> : leftIcon}
      <span>{children}</span>
    </button>
  );
});

// ---------------------------------------------------------------------------
// LinkButton — same look as Button, but uses react-router <Link>
// ---------------------------------------------------------------------------

interface LinkButtonProps extends LinkProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  leftIcon?: ReactNode;
}

export function LinkButton({
  variant = "secondary",
  size = "md",
  className,
  children,
  leftIcon,
  ...rest
}: LinkButtonProps) {
  return (
    <Link
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
        buttonVariants[variant],
        buttonSizes[size],
        className,
      )}
      {...rest}
    >
      {leftIcon}
      <span>{children}</span>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Form inputs
// ---------------------------------------------------------------------------

const inputBase =
  "w-full rounded-lg border border-ink-200 bg-white px-3.5 py-2.5 text-sm text-ink-900 placeholder:text-ink-400 transition-colors hover:border-ink-300 focus:border-accent-500 disabled:cursor-not-allowed disabled:bg-ink-50";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return <input ref={ref} className={cn(inputBase, className)} {...rest} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <select
        ref={ref}
        className={cn(
          inputBase,
          "appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 fill=%22none%22 viewBox=%220 0 20 20%22 stroke=%22%2371717a%22><path stroke-linecap=%22round%22 stroke-linejoin=%22round%22 stroke-width=%221.5%22 d=%22m6 8 4 4 4-4%22/></svg>')] bg-[right_0.6rem_center] bg-no-repeat pr-9",
          className,
        )}
        {...rest}
      >
        {children}
      </select>
    );
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return (
      <textarea
        ref={ref}
        className={cn(inputBase, "leading-6 resize-y min-h-[88px]", className)}
        {...rest}
      />
    );
  },
);

export function Field({
  label,
  hint,
  required,
  children,
  htmlFor,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <label className="block" htmlFor={htmlFor}>
      <span className="mb-1.5 block text-xs font-medium text-ink-700">
        {label}
        {required ? <span className="ml-0.5 text-accent-600">*</span> : null}
      </span>
      {children}
      {hint ? <span className="mt-1 block text-xs text-ink-500">{hint}</span> : null}
    </label>
  );
}

// ---------------------------------------------------------------------------
// Status pill
// ---------------------------------------------------------------------------

const statusStyles: Record<string, string> = {
  pending: "bg-ink-100 text-ink-700 border-ink-200",
  "in progress": "bg-accent-50 text-accent-700 border-accent-100",
  "under review": "bg-violet-50 text-violet-700 border-violet-100",
  "clarification needed": "bg-amber-50 text-amber-700 border-amber-100",
  responded: "bg-emerald-50 text-emerald-700 border-emerald-100",
  rejected: "bg-red-50 text-red-700 border-red-100",
};

export function StatusBadge({
  status,
  className,
  size = "sm",
}: {
  status: string;
  className?: string;
  size?: "sm" | "md";
}) {
  const key = status.toLowerCase();
  const style = statusStyles[key] ?? "bg-ink-100 text-ink-700 border-ink-200";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-3 py-1 text-xs",
        style,
        className,
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          key === "responded" && "bg-emerald-500",
          key === "rejected" && "bg-red-500",
          key === "clarification needed" && "bg-amber-500",
          key === "under review" && "bg-violet-500",
          key === "in progress" && "bg-accent-500",
          (!key || key === "pending") && "bg-ink-400",
        )}
      />
      {status}
    </span>
  );
}

export type { ButtonVariant, RequestStatus };

// ---------------------------------------------------------------------------
// Loading + error states
// ---------------------------------------------------------------------------

export function Spinner({ className }: { className?: string }) {
  return (
    <div className="flex w-full justify-center py-10">
      <span className={cn("spinner h-6 w-6", className)} />
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-3 h-10 w-10 rounded-full border border-dashed border-ink-300" />
      <h3 className="text-sm font-medium text-ink-900">{title}</h3>
      {description ? (
        <p className="mt-1 max-w-sm text-xs text-ink-500">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <span className="mt-0.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-red-500" />
      <span>{message}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page chrome
// ---------------------------------------------------------------------------

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
          {title}
        </h1>
        {description ? (
          <p className="mt-1 text-sm text-ink-500">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export function Container({
  children,
  size = "lg",
  className,
}: {
  children: ReactNode;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const widths = { sm: "max-w-2xl", md: "max-w-4xl", lg: "max-w-6xl" } as const;
  return (
    <main
      className={cn(
        "mx-auto w-full px-6 py-10 animate-fade-in",
        widths[size],
        className,
      )}
    >
      {children}
    </main>
  );
}
