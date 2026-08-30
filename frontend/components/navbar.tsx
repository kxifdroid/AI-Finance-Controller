"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useRef, useEffect } from "react";
import {
  BarChart3,
  Layers,
  AlertTriangle,
  MessageSquareText,
  TrendingUp,
  ShieldCheck,
  LogOut,
  User,
  ChevronDown,
  LogIn,
  Menu,
  X,
  Sun,
  Moon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { useTheme } from "@/lib/theme-context";
import { ProfileModal } from "./profile-modal";

const NAV_ITEMS = [
  { label: "Overview", href: "/", icon: BarChart3 },
  { label: "Transactions", href: "/transactions", icon: Layers },
  { label: "Exceptions", href: "/exceptions", icon: AlertTriangle },
  { label: "Forecast", href: "/forecast", icon: TrendingUp },
  { label: "Finance Q&A", href: "/chat", icon: MessageSquareText },
];

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  controller: "bg-primary/15 text-primary-light border-primary/30",
  auditor: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  demo: "bg-gray-700/50 text-gray-300 border-gray-600",
};

function getInitials(name?: string | null): string {
  if (!name) return "??";
  const parts = name.trim().split(" ");
  if (parts.length === 0 || !parts[0]) return "??";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function isNavActive(pathname: string, href: string): boolean {
  return pathname === href || (href !== "/" && pathname.startsWith(href));
}

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const { theme, resolvedTheme, toggleTheme } = useTheme();

  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-surface/90 backdrop-blur-md transition-colors">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">

        {/* Brand */}
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2.5 group" aria-label="AI Finance Controller home">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15 border border-primary/40 text-primary-light">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="leading-tight">
              <span className="block text-[15px] font-bold tracking-tight text-content">
                AI Finance Controller
              </span>
              <span className="block text-[11px] text-content-secondary font-medium">
                Financial Operations
              </span>
            </div>
          </Link>
        </div>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-1" aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isNavActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-colors focus-ring",
                  active
                    ? "bg-surface-elevated text-content font-semibold shadow-xs"
                    : "text-content-secondary hover:text-content hover:bg-surface-secondary"
                )}
              >
                <Icon className={cn("h-4 w-4", active ? "text-primary-light" : "text-content-muted")} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Right: status + theme toggle + user */}
        <div className="flex items-center gap-2.5">

          {/* Pipeline status indicator */}
          <div className="hidden sm:flex items-center gap-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/25 px-2.5 py-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <span>Pipeline Ready</span>
          </div>

          {/* Theme Toggle Button (Sun / Moon) */}
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={`Switch to ${resolvedTheme === "dark" ? "light" : "dark"} mode`}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface-secondary text-content-secondary hover:text-content hover:bg-surface-elevated transition-colors focus-ring"
            title={`Toggle ${resolvedTheme === "dark" ? "Light" : "Dark"} Mode`}
          >
            {resolvedTheme === "dark" ? (
              <Sun className="h-4 w-4 text-amber-400" />
            ) : (
              <Moon className="h-4 w-4 text-indigo-600" />
            )}
          </button>

          {isLoading ? (
            <div className="h-8 w-8 rounded-full bg-surface-secondary animate-pulse" />
          ) : isAuthenticated && user ? (
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                aria-label="Account menu"
                className="flex items-center gap-2.5 rounded-xl border border-border bg-surface-secondary px-2.5 py-1.5 text-xs hover:bg-surface-elevated transition-colors focus-ring"
              >
                <div className="h-7 w-7 rounded-full overflow-hidden flex items-center justify-center bg-primary/20 border border-primary/40 text-primary-light font-bold text-xs shrink-0">
                  {user.avatar_url ? (
                    <img
                      src={user.avatar_url.startsWith("http") ? user.avatar_url : `${process.env.NEXT_PUBLIC_API_URL || ""}${user.avatar_url}`}
                      alt={user.name}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    getInitials(user.name)
                  )}
                </div>
                <div className="hidden sm:block text-left">
                  <div className="font-semibold text-content leading-tight truncate max-w-[120px]">
                    {user.name ? user.name.split(" ")[0] : "User"}
                  </div>
                  <span className={cn("text-[10px] px-1.5 py-0.5 rounded border font-medium uppercase", ROLE_COLORS[user.role] || ROLE_COLORS["controller"])}>
                    {user.role}
                  </span>
                </div>
                <ChevronDown className={cn("h-3.5 w-3.5 text-content-muted transition-transform", menuOpen && "rotate-180")} />
              </button>

              {menuOpen && (
                <div role="menu" className="absolute right-0 mt-2 w-64 rounded-xl border border-border bg-surface shadow-2xl py-1 z-50">
                  <div className="px-4 py-3 border-b border-border">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-full overflow-hidden flex items-center justify-center bg-primary/20 border border-primary/40 text-primary-light font-bold text-sm shrink-0">
                        {user.avatar_url ? (
                          <img
                            src={user.avatar_url.startsWith("http") ? user.avatar_url : `${process.env.NEXT_PUBLIC_API_URL || ""}${user.avatar_url}`}
                            alt={user.name}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          getInitials(user.name)
                        )}
                      </div>
                      <div className="overflow-hidden">
                        <div className="font-semibold text-content text-sm truncate">{user.name}</div>
                        <div className="text-xs text-content-secondary truncate">{user.email}</div>
                        <div className={cn("text-[10px] px-1.5 py-0.5 rounded border inline-block mt-1 font-medium uppercase", ROLE_COLORS[user.role] || ROLE_COLORS["controller"])}>
                          {user.auth_provider === "google" ? "Google Account" : user.auth_provider === "demo" ? "Demo Account" : "Email Account"}
                        </div>
                      </div>
                    </div>
                  </div>
                  <button
                    role="menuitem"
                    onClick={() => { setProfileModalOpen(true); setMenuOpen(false); }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-xs text-content-secondary hover:bg-surface-secondary hover:text-content transition-colors"
                  >
                    <User className="h-4 w-4" />
                    Profile Settings
                  </button>
                  <button
                    role="menuitem"
                    onClick={handleLogout}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-xs text-content-secondary hover:bg-rose-500/10 hover:text-rose-500 transition-colors"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link
              href="/login"
              className="flex items-center gap-2 rounded-lg border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary-light hover:bg-primary/20 transition-colors focus-ring"
            >
              <LogIn className="h-4 w-4" />
              Sign In
            </Link>
          )}

          {/* Mobile menu toggle */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileOpen}
            className="md:hidden flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface-secondary text-content-secondary hover:text-content hover:bg-surface-elevated transition-colors focus-ring"
          >
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Mobile navigation drawer */}
      {mobileOpen && (
        <div className="md:hidden border-t border-border bg-surface px-4 py-3 space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isNavActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors",
                  active
                    ? "bg-surface-elevated text-content font-semibold"
                    : "text-content-secondary hover:text-content hover:bg-surface-secondary"
                )}
              >
                <Icon className={cn("h-4 w-4", active ? "text-primary-light" : "text-content-muted")} />
                {item.label}
              </Link>
            );
          })}
        </div>
      )}

      {profileModalOpen && (
        <ProfileModal onClose={() => setProfileModalOpen(false)} />
      )}
    </header>
  );
}
