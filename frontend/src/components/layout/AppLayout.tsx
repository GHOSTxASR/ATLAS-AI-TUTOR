import { NavLink } from "react-router-dom";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Brain,
  ChartLine,
  Files,
  LayoutDashboard,
  MessageSquare,
  Network,
  Route,
  Settings,
  BookOpen,
  Search,
  Menu,
  X,
  User,
  ChevronsUpDown,
  Sparkles,
  HelpCircle,
} from "lucide-react";
import { GlobalSearchModal } from "../common/GlobalSearchModal";
import { LiquidBackground } from "../common/LiquidBackground";
import { useThemeStore } from "../../stores/themeStore";
import { useProfileStore } from "../../stores/profileStore";
import { useFocusTrap } from "../../hooks/useFocusTrap";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/chat", label: "AI Tutor", icon: MessageSquare },
  { to: "/roadmap", label: "Roadmap", icon: Route },
  { to: "/notes", label: "Notes", icon: BookOpen },
  { to: "/documents", label: "Library", icon: Files },
  { to: "/graph", label: "Graph", icon: Network },
  { to: "/quiz", label: "Quizzes", icon: HelpCircle },
  { to: "/analytics", label: "Analytics", icon: ChartLine },
  { to: "/memory", label: "Memory", icon: Brain },
  { to: "/settings", label: "Settings", icon: Settings },
];

interface AppLayoutProps {
  children: ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const { initializeTheme } = useThemeStore();
  const { activeProfileId, profiles, setActiveProfile, loadProfiles } = useProfileStore();
  const mobileMenuRef = useRef<HTMLElement>(null);
  useFocusTrap(mobileMenuOpen, mobileMenuRef, () => setMobileMenuOpen(false));
  const activeProfile = profiles.find((p) => p.id === activeProfileId);

  useEffect(() => {
    initializeTheme();
  }, [initializeTheme]);

  useEffect(() => {
    loadProfiles();
  }, [loadProfiles]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileMenuOpen(false);
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [mobileMenuOpen]);

  // Global Keyboard Shortcut for Search (Cmd+K / Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    // The shell owns the viewport; `main` is the only scrolling region. The
    // previous `min-h-screen ... overflow-x-hidden` made this element a scroll
    // container, which silently disabled `position: sticky` on the sidebar --
    // the whole rail scrolled away with the page.
    <div className="h-screen overflow-hidden bg-surface dark:bg-[#131314] text-on-surface dark:text-[#e5e2e3] relative flex flex-col md:flex-row antialiased selection:bg-primary/20 selection:text-primary">
      {/* Liquid WebGL Canvas Background */}
      <LiquidBackground />

      {/* Mobile Top Header */}
      <header className="md:hidden shrink-0 z-30 flex items-center justify-between px-4 py-3 bg-surface/75 dark:bg-[#131314]/80 backdrop-blur-xl border-b border-glass-border">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
            aria-expanded={mobileMenuOpen}
            className="p-2 rounded-lg text-on-surface-variant hover:bg-surface-bright/20 focus-visible:ring-2 focus-visible:ring-primary transition"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-md bg-deep-slate-teal text-luminous-highlight border border-glass-border flex items-center justify-center font-bold text-xs shadow-sm">
              <Sparkles className="w-4 h-4" />
            </div>
            <span className="font-editorial text-xl font-normal tracking-tight text-on-surface">
              Atlas
            </span>
          </div>
        </div>

        {/* Theme lives in Settings, next to the rest of the appearance
            controls. A second toggle here was the same setting in two places. */}
        <button
          onClick={() => setSearchOpen(true)}
          aria-label="Search"
          className="p-2 rounded-lg text-on-surface-variant hover:bg-surface-bright/20 transition"
        >
          <Search className="w-4 h-4" />
        </button>
      </header>

      {/* Mobile Drawer Backdrop Overlay */}
      {mobileMenuOpen && (
        <div
          className="md:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* High-Density Glass Rail Navigation (Desktop + Mobile Drawer) */}
      <aside
        ref={mobileMenuRef}
        role={mobileMenuOpen ? "dialog" : undefined}
        aria-modal={mobileMenuOpen ? true : undefined}
        aria-label={mobileMenuOpen ? "Mobile navigation menu" : "Main Navigation"}
        className={`fixed md:relative inset-y-0 left-0 z-40 md:z-20 h-full w-64 md:w-60 lg:w-64 shrink-0 glass-panel border-r border-glass-border flex flex-col p-3.5 transition-transform duration-300 ease-in-out ${
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        {/* min-h-0 lets this region shrink and scroll on short viewports
            instead of pushing the profile switcher off-screen. */}
        <div className="flex-1 min-h-0 overflow-y-auto space-y-4">
          {/* Brand Logo */}
          <div className="flex items-center justify-between px-2 pt-1 pb-1">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-deep-slate-teal text-luminous-highlight border border-glass-border flex items-center justify-center shadow-[0_0_12px_rgba(var(--accent-rgb),0.2)]">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <span className="font-editorial text-2xl tracking-tight text-on-surface block leading-none">
                  Atlas
                </span>
                <span className="text-[10px] text-on-surface-variant/80 font-medium tracking-wider uppercase block mt-0.5">
                  AI Learning Platform
                </span>
              </div>
            </div>
            {/* Close button on mobile */}
            <button
              onClick={() => setMobileMenuOpen(false)}
              className="md:hidden p-1.5 rounded-md text-on-surface-variant hover:bg-surface-bright/20"
              aria-label="Close menu"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Quick Search Trigger */}
          <button
            onClick={() => setSearchOpen(true)}
            className="hidden md:flex w-full items-center justify-between px-3 py-2 rounded-lg bg-surface-container/40 hover:bg-surface-container-high/60 border border-glass-border text-on-surface-variant text-xs transition duration-200 group"
          >
            <div className="flex items-center gap-2">
              <Search className="w-3.5 h-3.5 group-hover:text-luminous-highlight transition-colors" />
              <span className="font-sans">Search workstation...</span>
            </div>
            <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-surface-container-highest/60 border border-glass-border font-mono text-on-surface-variant">
              ⌘K
            </kbd>
          </button>

          {/* Navigation Links */}
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => setMobileMenuOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200 group ${
                      isActive
                        ? "bg-surface-container/60 text-luminous-highlight border border-glass-border shadow-[0_0_10px_rgba(var(--accent-rgb),0.15)] luminous-active"
                        : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container/30 border border-transparent"
                    }`
                  }
                >
                  <Icon className="w-4 h-4 shrink-0 transition-transform group-hover:scale-105" />
                  <span className="font-sans text-xs tracking-tight">{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Footer / Profile Switcher.
            The badge and the <select> both rendered the profile name, so it
            appeared twice side by side. The select is now an invisible overlay
            covering the whole row: one visible label, still keyboard-operable. */}
        <div className="shrink-0 pt-3 mt-3 border-t border-glass-border">
          <div className="relative flex items-center gap-2 px-2 py-1.5 rounded-lg bg-surface-container/30 border border-glass-border focus-within:border-primary transition-colors">
            <div className="w-6 h-6 rounded-full bg-primary-container/40 text-primary border border-glass-border flex items-center justify-center shrink-0">
              <User className="w-3 h-3" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-on-surface truncate">
                {activeProfile ? activeProfile.name : "Learner"}
              </p>
              <p className="text-[10px] text-on-surface-variant truncate">
                {activeProfile ? activeProfile.profile_type : "No Profile"}
              </p>
            </div>
            {profiles.length > 1 && (
              <>
                <ChevronsUpDown
                  className="w-3.5 h-3.5 text-on-surface-variant shrink-0"
                  aria-hidden="true"
                />
                <select
                  value={activeProfileId || ""}
                  onChange={(e) => setActiveProfile(e.target.value)}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  aria-label="Switch profile"
                >
                  {profiles.map((p) => (
                    <option key={p.id} value={p.id} className="bg-surface text-on-surface">
                      {p.name} — {p.profile_type}
                    </option>
                  ))}
                </select>
              </>
            )}
          </div>
        </div>
      </aside>

      {/* Main Workspace Area (Floating Glass Panels).
          The only scrolling region, so the nav rail stays put. The inner
          wrapper carries the max-width so the scrollbar sits at the edge. */}
      <main className="flex-1 min-w-0 relative z-10 overflow-y-auto overflow-x-hidden">
        <div className="mx-auto w-full min-w-0 max-w-7xl min-h-full flex flex-col p-4 sm:p-6 lg:p-8">
          {children}
        </div>
      </main>

      {/* Global Search Dialog Modal */}
      <GlobalSearchModal isOpen={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
