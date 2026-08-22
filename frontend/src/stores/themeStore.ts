import { create } from "zustand";

export type ThemeMode = "light" | "dark" | "system";

interface ThemeState {
  theme: ThemeMode;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
  initializeTheme: () => void;
}

const STORAGE_KEY = "learningos_theme";

function getSystemTheme(): "light" | "dark" {
  if (typeof window !== "undefined" && window.matchMedia) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return "dark";
}

function applyThemeClass(resolved: "light" | "dark") {
  if (typeof document !== "undefined") {
    const root = document.documentElement;
    if (resolved === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    root.setAttribute("data-theme", resolved);
  }
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: (typeof localStorage !== "undefined" ? (localStorage.getItem(STORAGE_KEY) as ThemeMode) : null) || "system",
  resolvedTheme: "dark",

  setTheme: (theme: ThemeMode) => {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(STORAGE_KEY, theme);
    }
    const resolved = theme === "system" ? getSystemTheme() : theme;
    applyThemeClass(resolved);
    set({ theme, resolvedTheme: resolved });
  },

  toggleTheme: () => {
    const current = get().resolvedTheme;
    const next = current === "dark" ? "light" : "dark";
    get().setTheme(next);
  },

  initializeTheme: () => {
    const saved = (typeof localStorage !== "undefined" ? (localStorage.getItem(STORAGE_KEY) as ThemeMode) : null) || "system";
    const resolved = saved === "system" ? getSystemTheme() : saved;
    applyThemeClass(resolved);
    set({ theme: saved, resolvedTheme: resolved });

    // Listen for OS theme changes if in system mode
    if (typeof window !== "undefined" && window.matchMedia) {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      mediaQuery.addEventListener("change", (e) => {
        if (get().theme === "system") {
          const newResolved = e.matches ? "dark" : "light";
          applyThemeClass(newResolved);
          set({ resolvedTheme: newResolved });
        }
      });
    }
  },
}));
