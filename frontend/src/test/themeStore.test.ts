import { describe, it, expect, beforeEach } from "vitest";
import { useThemeStore } from "../stores/themeStore";

describe("useThemeStore Unit Tests", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
    useThemeStore.setState({ theme: "system", resolvedTheme: "dark" });
  });

  it("initializes with default system theme", () => {
    const { theme } = useThemeStore.getState();
    expect(theme).toBe("system");
  });

  it("updates theme to dark and applies dark class to document", () => {
    useThemeStore.getState().setTheme("dark");
    expect(useThemeStore.getState().theme).toBe("dark");
    expect(useThemeStore.getState().resolvedTheme).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("atlas_theme")).toBe("dark");
  });

  it("updates theme to light and removes dark class from document", () => {
    useThemeStore.getState().setTheme("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    useThemeStore.getState().setTheme("light");
    expect(useThemeStore.getState().theme).toBe("light");
    expect(useThemeStore.getState().resolvedTheme).toBe("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("atlas_theme")).toBe("light");
  });

  it("toggleTheme switches between light and dark modes", () => {
    useThemeStore.getState().setTheme("light");
    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().theme).toBe("dark");

    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().theme).toBe("light");
  });
});

describe("theme storage key rename", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("adopts a theme saved under the pre-rename key", () => {
    localStorage.setItem("learningos_theme", "light");

    useThemeStore.getState().initializeTheme();

    expect(useThemeStore.getState().theme).toBe("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("moves the legacy value onto the new key and drops the old one", () => {
    localStorage.setItem("learningos_theme", "dark");

    useThemeStore.getState().initializeTheme();

    expect(localStorage.getItem("atlas_theme")).toBe("dark");
    expect(localStorage.getItem("learningos_theme")).toBeNull();
  });

  it("keeps the current key when both are present", () => {
    localStorage.setItem("learningos_theme", "dark");
    localStorage.setItem("atlas_theme", "light");

    useThemeStore.getState().initializeTheme();

    expect(useThemeStore.getState().theme).toBe("light");
  });
});
