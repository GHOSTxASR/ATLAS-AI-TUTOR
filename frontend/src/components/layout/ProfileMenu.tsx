import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, ChevronsUpDown, Plus, User } from "lucide-react";

import { useProfileStore } from "../../stores/profileStore";

interface ProfileMenuProps {
  /** Icon-only presentation for the collapsed desktop rail. */
  collapsed?: boolean;
}

const pad = (n: number) => String(n + 1).padStart(2, "0");

/**
 * Profile switcher.
 *
 * Replaces a transparent `<select>` stretched over the row, which gave no
 * visible affordance and rendered the OS dropdown -- a control that cannot be
 * styled and looked nothing like the rest of the app.
 */
export function ProfileMenu({ collapsed = false }: ProfileMenuProps) {
  const navigate = useNavigate();
  const { profiles, activeProfileId, setActiveProfile } = useProfileStore();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  const activeProfile = profiles.find((p) => p.id === activeProfileId);

  const close = (returnFocus = true) => {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  };

  // Pointerdown rather than click: a click listener fires after the menu has
  // already handled its own click, which closes and reopens in one gesture.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        close();
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  // Move focus into the menu on open so it is operable from the keyboard.
  useEffect(() => {
    if (!open) return;
    const first = menuRef.current?.querySelector<HTMLElement>(
      '[role="menuitemradio"][aria-checked="true"], [role="menuitemradio"]',
    );
    first?.focus();
  }, [open]);

  const onMenuKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const items = Array.from(
      menuRef.current?.querySelectorAll<HTMLElement>('[role^="menuitem"]') ?? [],
    );
    if (!items.length) return;
    const i = items.indexOf(document.activeElement as HTMLElement);
    const next = e.key === "ArrowDown" ? i + 1 : i - 1;
    items[(next + items.length) % items.length].focus();
  };

  const choose = (id: string) => {
    setActiveProfile(id);
    close();
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={
          activeProfile
            ? `Current profile: ${activeProfile.name}. Switch profile`
            : "Choose a profile"
        }
        title={collapsed && activeProfile ? activeProfile.name : undefined}
        className={`atlas-hover flex w-full items-center gap-2.5 px-3 py-2.5 border border-glass-border bg-surface-container/30 ${
          collapsed ? "md:justify-center md:gap-0 md:px-0" : ""
        } ${open ? "border-primary" : ""}`}
      >
        <span className="flex h-6 w-6 shrink-0 items-center justify-center border border-glass-border bg-primary-container/40 text-primary">
          <User className="h-3 w-3" aria-hidden="true" />
        </span>
        <span className={collapsed ? "contents md:hidden" : "contents"}>
          <>
            <span className="min-w-0 flex-1 text-left">
              <span className="block truncate text-xs font-medium text-on-surface">
                {activeProfile ? activeProfile.name : "Learner"}
              </span>
              <span className="block truncate font-mono text-[10px] uppercase tracking-[0.14em] text-on-surface-variant">
                {activeProfile ? activeProfile.profile_type : "No profile"}
              </span>
            </span>
            <ChevronsUpDown
              className="h-3.5 w-3.5 shrink-0 text-on-surface-variant"
              aria-hidden="true"
            />
          </>
        </span>
      </button>

      {open && (
        <div
          ref={menuRef}
          id={menuId}
          role="menu"
          aria-label="Switch profile"
          onKeyDown={onMenuKeyDown}
          // Opens upward: the trigger sits at the bottom of the rail.
          className={`absolute bottom-full z-50 mb-1 max-h-[60vh] overflow-y-auto inset-x-0 border border-t-2 border-glass-border border-t-primary bg-surface-container-high shadow-[0_-8px_30px_rgba(0,0,0,0.45)] ${
            collapsed ? "md:left-0 md:right-auto md:w-64" : ""
          }`}
        >
          <p className="atlas-label border-b border-glass-border px-3 py-2.5">
            Switch profile
          </p>

          {profiles.map((p, i) => {
            const isActive = p.id === activeProfileId;
            return (
              <button
                key={p.id}
                type="button"
                role="menuitemradio"
                aria-checked={isActive}
                onClick={() => choose(p.id)}
                className={`atlas-hover flex w-full items-center gap-3 border-b border-glass-border px-3 py-2.5 text-left ${
                  isActive ? "bg-surface-container" : ""
                }`}
              >
                <span
                  className="shrink-0 font-mono text-[10px] tracking-[0.16em] text-primary"
                  aria-hidden="true"
                >
                  [ {pad(i)} ]
                </span>
                <span className="min-w-0 flex-1">
                  <span
                    className={`block truncate text-xs ${
                      isActive ? "text-luminous-highlight" : "text-on-surface"
                    }`}
                  >
                    {p.name}
                  </span>
                  <span className="block truncate font-mono text-[10px] uppercase tracking-[0.14em] text-on-surface-variant">
                    {p.profile_type}
                  </span>
                </span>
                {isActive && (
                  <Check className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
                )}
              </button>
            );
          })}

          <button
            type="button"
            role="menuitem"
            onClick={() => {
              close(false);
              navigate("/setup");
            }}
            className="atlas-hover flex w-full items-center gap-3 px-3 py-2.5 text-left"
          >
            <Plus className="h-3.5 w-3.5 shrink-0 text-on-surface-variant" aria-hidden="true" />
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-on-surface-variant">
              New / manage profiles
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
