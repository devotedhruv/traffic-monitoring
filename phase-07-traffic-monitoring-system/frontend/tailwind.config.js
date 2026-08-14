/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "rgb(var(--color-page) / <alpha-value>)",
        sidebar: "rgb(var(--color-sidebar) / <alpha-value>)",
        header: "rgb(var(--color-header) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        "surface-secondary": "rgb(var(--color-surface-secondary) / <alpha-value>)",
        card: "rgb(var(--color-card) / <alpha-value>)",
        elevated: "rgb(var(--color-elevated) / <alpha-value>)",
        line: "rgb(var(--color-border) / <alpha-value>)",
        border: "rgb(var(--color-border) / <alpha-value>)",
        "border-strong": "rgb(var(--color-border-strong) / <alpha-value>)",
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        secondary: "rgb(var(--color-secondary) / <alpha-value>)",
        primary: "rgb(var(--color-primary) / <alpha-value>)",
        "primary-hover": "rgb(var(--color-primary-hover) / <alpha-value>)",
        "primary-soft": "rgb(var(--color-primary-soft) / <alpha-value>)",
        "on-primary": "rgb(var(--color-on-primary) / <alpha-value>)",
        cyan: "rgb(var(--color-cyan) / <alpha-value>)",
        "cyan-dark": "rgb(var(--color-cyan-dark) / <alpha-value>)",
        success: "rgb(var(--color-success) / <alpha-value>)",
        amber: "rgb(var(--color-warning) / <alpha-value>)",
        warning: "rgb(var(--color-warning) / <alpha-value>)",
        danger: "rgb(var(--color-danger) / <alpha-value>)",
        "danger-dark": "rgb(var(--color-danger-soft) / <alpha-value>)",
        info: "rgb(var(--color-info) / <alpha-value>)",
        purple: "rgb(var(--color-purple) / <alpha-value>)"
      },
      fontFamily: { sans: ["Poppins", "Segoe UI", "ui-sans-serif", "system-ui", "sans-serif"] },
      boxShadow: { panel: "var(--shadow-panel)", card: "var(--shadow-card)" }
    }
  },
  plugins: []
};
