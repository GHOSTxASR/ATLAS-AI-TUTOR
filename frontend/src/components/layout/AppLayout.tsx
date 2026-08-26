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
  Sparkles,
  HelpCircle,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { GlobalSearchModal } from "../common/GlobalSearchModal";
import { ParticleSwarm } from "../landing/ParticleSwarm";
import { PageTransition } from "./PageTransition";
import { ProfileMenu } from "./ProfileMenu";
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

const SIDEBAR_KEY = "atlas_sidebar_collapsed";

interface AppLayoutProps {
  children: ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  // Read synchronously on first render: resolving this in an effect would show
  // the expanded rail for a frame and then snap it shut.
  const [collapsed, setCollapsed] = useState(
    () => typeof localStorage !== "undefined" && localStorage.getItem(SIDEBAR_KEY) === "1",
  );

  const { initializeTheme } = useThemeStore();
  const { loadProfiles } = useProfileStore();
  const mobileMenuRef = useRef<HTMLElement>(null);
  useFocusTrap(mobileMenuOpen, mobileMenuRef, () => setMobileMenuOpen(false));

  useEffect(() => {
    initializeTheme();
  }, [initializeTheme]);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

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
      {/* Same ambient field as the landing page, so the app reads as one product. */}
      <ParticleSwarm />

      {/* Mobile Top Header */}
      <header className="md:hidden shrink-0 z-30 flex items-center justify-between px-4 py-3 bg-surface/75 dark:bg-[#131314]/80 backdrop-blur-xl border-b border-glass-border">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
            aria-expanded={mobileMenuOpen}
            className="p-2 text-on-surface-variant hover:bg-surface-bright/20 focus-visible:ring-2 focus-visible:ring-primary transition"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-primary-container/40 text-luminous-highlight border border-glass-border flex items-center justify-center font-bold text-xs shadow-sm">
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
          className="p-2 text-on-surface-variant hover:bg-surface-bright/20 transition"
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
        className={`fixed md:relative inset-y-0 left-0 z-40 md:z-20 h-full w-64 shrink-0 glass-panel border-r border-glass-border flex flex-col p-3.5 transition-[transform,width] duration-300 ease-in-out ${
          collapsed ? "md:w-[4.5rem] md:px-2" : "md:w-60 lg:w-64"
        } ${
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        {/* min-h-0 lets this region shrink and scroll on short viewports
            instead of pushing the profile switcher off-screen. */}
        <div className="flex-1 min-h-0 overflow-y-auto space-y-4">
          {/* Brand Logo */}
          <div className={`flex items-center justify-between px-2 pt-1 pb-1 ${collapsed ? "md:justify-center md:px-0" : ""}`}>
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 shrink-0 bg-primary-container/40 text-luminous-highlight border border-glass-border flex items-center justify-center shadow-[0_0_12px_rgba(var(--accent-rgb),0.2)]">
                <Sparkles className="w-4 h-4" />
              </div>
              <span
                className={`font-editorial text-2xl tracking-tight text-on-surface leading-none ${
                  collapsed ? "md:hidden" : ""
                }`}
              >
                Atlas
              </span>
            </div>
            {/* Close button on mobile */}
            <button
              onClick={() => setMobileMenuOpen(false)}
              className="md:hidden p-1.5 text-on-surface-variant hover:bg-surface-bright/20"
              aria-label="Close menu"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Quick Search Trigger */}
          <button
            onClick={() => setSearchOpen(true)}
            aria-label="Search"
            title={collapsed ? "Search" : undefined}
            className={`atlas-hover hidden md:flex w-full items-center py-2.5 bg-surface-container/40 border border-glass-border text-on-surface-variant group ${
              collapsed ? "md:justify-center md:px-0" : "justify-between px-3"
            }`}
          >
            <span className="flex items-center gap-2">
              <Search className="w-3.5 h-3.5 group-hover:text-luminous-highlight transition-colors" />
              <span className={`font-mono text-[11px] uppercase tracking-[0.14em] ${collapsed ? "md:hidden" : ""}`}>
                Search
              </span>
            </span>
            <kbd
              className={`text-[10px] px-1.5 py-0.5 bg-surface-container-highest/60 border border-glass-border font-mono text-on-surface-variant ${
                collapsed ? "md:hidden" : ""
              }`}
            >
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
                  // Selection and hover both come from .atlas-nav-item, keyed off
                  // the aria-current NavLink already sets.
                  title={collapsed ? item.label : undefined}
                  className={`atlas-nav-item group flex items-center gap-3 px-3 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-on-surface-variant ${
                    collapsed ? "md:justify-center md:gap-0 md:px-0" : ""
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span className={collapsed ? "md:hidden" : ""}>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        <div className="shrink-0 pt-3 mt-3 border-t border-glass-border space-y-2">
          <ProfileMenu collapsed={collapsed} />

          {/* Desktop only: the mobile rail is a drawer that closes outright. */}
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-pressed={collapsed}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={`atlas-hover hidden md:flex w-full items-center gap-3 px-3 py-2 border border-transparent font-mono text-[10px] uppercase tracking-[0.16em] text-on-surface-variant ${
              collapsed ? "md:justify-center md:gap-0 md:px-0" : ""
            }`}
          >
            {collapsed ? (
              <PanelLeftOpen className="w-4 h-4 shrink-0" aria-hidden="true" />
            ) : (
              <PanelLeftClose className="w-4 h-4 shrink-0" aria-hidden="true" />
            )}
            <span className={collapsed ? "md:hidden" : ""}>Collapse</span>
          </button>
        </div>
      </aside>

      {/* Main Workspace Area (Floating Glass Panels).
          The only scrolling region, so the nav rail stays put. The inner
          wrapper carries the max-width so the scrollbar sits at the edge. */}
      <main className="flex-1 min-w-0 relative z-10 overflow-y-auto overflow-x-hidden">
        <div className="w-full min-w-0 min-h-full flex flex-col p-4 sm:p-6 lg:p-8">
          <PageTransition>{children}</PageTransition>
        </div>
      </main>

      {/* Global Search Dialog Modal */}
      <GlobalSearchModal isOpen={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
