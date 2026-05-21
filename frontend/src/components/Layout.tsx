import { Link, NavLink, useNavigate, Outlet } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/cn";

const navLinkBase =
  "inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md transition-colors";

function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink-900 text-white">
        {/* Logo mark — abstract document */}
        <svg
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M3 2.5a1 1 0 0 1 1-1h6.5L13 4v9.5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-11Z"
            stroke="currentColor"
            strokeWidth="1.4"
          />
          <path
            d="M5.5 6.5h5M5.5 9h5M5.5 11.5h3"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      </span>
      <div className="flex flex-col leading-none">
        <span className="text-sm font-semibold tracking-tight text-ink-900">
          RTI4All
        </span>
        <span className="mt-0.5 text-[10px] uppercase tracking-[0.12em] text-ink-500">
          Automated Transparency
        </span>
      </div>
    </Link>
  );
}

function NavItem({ to, label, end }: { to: string; label: string; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          navLinkBase,
          isActive
            ? "bg-ink-100 text-ink-900"
            : "text-ink-600 hover:text-ink-900 hover:bg-ink-50",
        )
      }
    >
      {label}
    </NavLink>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) {
    return (
      <div className="flex items-center gap-2">
        <NavLink
          to="/login"
          className={({ isActive }) =>
            cn(
              navLinkBase,
              isActive
                ? "bg-ink-100 text-ink-900"
                : "text-ink-600 hover:text-ink-900 hover:bg-ink-50",
            )
          }
        >
          Sign in
        </NavLink>
        <Link
          to="/signup"
          className="inline-flex h-8 items-center rounded-md bg-ink-900 px-3 text-sm font-medium text-white transition-colors hover:bg-ink-800"
        >
          Create account
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 border-l border-ink-200 pl-4">
      <div className="text-right">
        <div className="text-xs font-medium text-ink-900">{user.full_name}</div>
        <div className="text-[11px] text-ink-500">{user.email}</div>
      </div>
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-ink-100 text-xs font-semibold uppercase text-ink-700">
        {user.full_name.slice(0, 1)}
      </div>
      <button
        type="button"
        onClick={() => {
          logout();
          navigate("/");
        }}
        className="text-xs text-ink-500 transition-colors hover:text-ink-900"
      >
        Sign out
      </button>
    </div>
  );
}

export function Navbar() {
  const { user } = useAuth();
  return (
    <nav className="sticky top-0 z-30 border-b border-ink-200 bg-white/85 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between gap-6 px-6">
        <Brand />
        <div className="flex items-center gap-1">
          <NavItem to="/" label="Home" end />
          {/* `end` on "My requests" so it doesn't stay active for /requests/new
             or /requests/:id detail pages. */}
          {user ? <NavItem to="/requests" label="My requests" end /> : null}
          {user ? <NavItem to="/requests/new" label="File a request" /> : null}
          <NavItem to="/departments" label="Departments" />
          <NavItem to="/faqs" label="FAQs" />
          {user?.is_admin ? <NavItem to="/admin" label="Admin" /> : null}
        </div>
        <UserMenu />
      </div>
    </nav>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-ink-200 bg-white py-6">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 text-xs text-ink-500">
        <div>
          <span className="font-medium text-ink-700">RTI4All</span>
          <span className="mx-2 text-ink-300">·</span>
          <span className="uppercase tracking-[0.12em]">Automated Transparency</span>
        </div>
        <div>
          Mandated by the Right to Information Act (Act No. 1/2014)
        </div>
      </div>
    </footer>
  );
}

export function AppShell() {
  return (
    <div className="flex min-h-full flex-col">
      <Navbar />
      <div className="flex-1">
        <Outlet />
      </div>
      <Footer />
    </div>
  );
}
