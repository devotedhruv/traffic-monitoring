/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "rgb(var(--color-page) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        card: "rgb(var(--color-card) / <alpha-value>)",
        elevated: "rgb(var(--color-elevated) / <alpha-value>)",
        line: "rgb(var(--color-line) / <alpha-value>)",
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        cyan: "rgb(var(--color-cyan) / <alpha-value>)",
        "cyan-dark": "rgb(var(--color-cyan-dark) / <alpha-value>)",
        success: "rgb(var(--color-success) / <alpha-value>)",
        amber: "rgb(var(--color-amber) / <alpha-value>)",
        danger: "rgb(var(--color-danger) / <alpha-value>)",
        "danger-dark": "rgb(var(--color-danger-dark) / <alpha-value>)"
      },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"] },
      boxShadow: { panel: "0 18px 45px rgb(0 0 0 / 0.18)" }
    }
  },
  plugins: []
};
