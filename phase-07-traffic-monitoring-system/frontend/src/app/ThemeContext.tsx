import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";

export type ThemePreference = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

interface ThemeContextValue {
  preference: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setPreference: (theme: ThemePreference) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    window.localStorage.removeItem("trafficops-theme");
    document.documentElement.classList.remove("dark");
    document.documentElement.dataset.theme = "light";
    document.documentElement.style.colorScheme = "light";
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", "#F4F6F8");
  }, []);

  const value = useMemo<ThemeContextValue>(() => ({
    preference: "light",
    resolvedTheme: "light",
    setPreference: () => undefined,
    toggleTheme: () => undefined
  }), []);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used within ThemeProvider");
  return value;
}
