"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useState, useRef, useEffect } from "react";
import { 
  BarChart3, 
  Layers, 
  AlertTriangle, 
  MessageSquareText, 
  TrendingUp, 
  ShieldCheck,
  Cpu,
  LogOut,
  User,
  ChevronDown,
  LogIn,
  Upload,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { ProfileModal } from "./profile-modal";

const NAV_ITEMS = [
  { label: "Dashboard",     href: "/",            icon: BarChart3 },
  { label: "Transactions",  href: "/transactions", icon: Layers },
  { label: "Exceptions",    href: "/exceptions",   icon: AlertTriangle },
  { label: "Finance Q&A",   href: "/chat",         icon: MessageSquareText },
  { label: "Cash Forecast", href: "/forecast",     icon: TrendingUp },
];

const ROLE_COLORS: Record<string, string> = {
  admin:      "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  controller: "bg-primary/15 text-primary-light border-primary/30",
  auditor:    "bg-amber-500/15 text-amber-300 border-amber-500/30",
  demo:       "bg-gray-700/50 text-gray-300 border-gray-600",
};

// Derive initials from name for avatar fallback
function getInitials(name?: string | null): string {
  if (!name) return "??";
  const parts = name.trim().split(" ");
  if (parts.length === 0 || !parts[0]) return "??";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function Navbar() {
  const pathname = usePathname();
  const router   = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();

  const [menuOpen, setMenuOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/80 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        
        {/* Brand */}
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/20 border border-primary/40 text-primary-light group-hover:scale-105 transition-transform">
              <ShieldCheck className="h-5 w-5 text-primary-light" />
            </div>
            <div>
              <span className="text-base font-bold tracking-tight text-white flex items-center gap-1.5">
                AI Finance Controller
              </span>
              <span className="block text-[10px] text-gray-400 font-mono tracking-wider">
                FINANCIAL OPERATIONS AGENT
              </span>
            </div>
          </Link>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all",
                  isActive
                    ? "bg-primary/20 text-white border border-primary/40 font-semibold shadow-sm"
                    : "text-gray-400 hover:text-white hover:bg-gray-800/60 border border-transparent"
                )}
              >
                <Icon className={cn("h-4 w-4", isActive ? "text-primary-light" : "text-gray-400")} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Right Side: Engine Status + User Menu */}
        <div className="flex items-center gap-3">
          
          {/* Engine Status Badge */}
          <div className="hidden sm:flex items-center gap-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-1 text-[11px] font-medium text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <Cpu className="h-3 w-3" />
            <span>Pipeline Ready</span>
          </div>

          {/* Auth Section */}
          {isLoading ? (
            <div className="h-8 w-8 rounded-full bg-gray-800 animate-pulse" />
          ) : isAuthenticated && user ? (
            // ---- User Profile Dropdown ----
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="flex items-center gap-2.5 rounded-xl border border-border bg-card/80 px-2.5 py-1.5 text-xs hover:bg-gray-800 transition-all"
              >
                {/* Avatar */}
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

                {/* Name + Role */}
                <div className="hidden sm:block text-left">
                  <div className="font-semibold text-white leading-tight truncate max-w-[120px]">
                    {user.name ? user.name.split(" ")[0] : "User"}
                  </div>
                  <span className={cn("text-[10px] px-1.5 py-0.5 rounded border font-mono uppercase", ROLE_COLORS[user.role] || ROLE_COLORS["controller"])}>
                    {user.role}
                  </span>
                </div>

                <ChevronDown className={cn("h-3.5 w-3.5 text-gray-400 transition-transform", menuOpen && "rotate-180")} />
              </button>

              {/* Dropdown Panel */}
              {menuOpen && (
                <div className="absolute right-0 mt-2 w-64 rounded-xl border border-border bg-card shadow-2xl py-1 z-50">
                  
                  {/* Profile Header */}
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
                        <div className="font-semibold text-white text-sm truncate">{user.name}</div>
                        <div className="text-xs text-gray-400 truncate">{user.email}</div>
                        <div className={cn("text-[10px] px-1.5 py-0.5 rounded border inline-block mt-1 font-mono uppercase", ROLE_COLORS[user.role] || ROLE_COLORS["controller"])}>
                          {user.auth_provider === "google" ? "🔵 Google Account" : user.auth_provider === "demo" ? "🔶 Demo Account" : "✉ Email Account"}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Profile Settings */}
                  <button
                    onClick={() => { setProfileModalOpen(true); setMenuOpen(false); }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-xs text-gray-300 hover:bg-gray-800 transition-colors"
                  >
                    <User className="h-4 w-4" />
                    Profile Settings
                  </button>

                  {/* Sign Out */}
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-xs text-gray-300 hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            // ---- Sign In Button ----
            <Link
              href="/login"
              className="flex items-center gap-2 rounded-lg border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary-light hover:bg-primary/20 transition-all"
            >
              <LogIn className="h-4 w-4" />
              Sign In
            </Link>
          )}

        </div>
      </div>
      
      {profileModalOpen && (
        <ProfileModal onClose={() => setProfileModalOpen(false)} />
      )}
    </header>
  );
}
