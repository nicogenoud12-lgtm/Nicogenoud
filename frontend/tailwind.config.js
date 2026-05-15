/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--c-bg) / <alpha-value>)",
        surface: "rgb(var(--c-surface) / <alpha-value>)",
        surfaceAlt: "rgb(var(--c-surface-alt) / <alpha-value>)",
        border: "rgb(var(--c-border) / <alpha-value>)",
        text: "rgb(var(--c-text) / <alpha-value>)",
        textMuted: "rgb(var(--c-text-muted) / <alpha-value>)",
        accent: "rgb(var(--c-accent) / <alpha-value>)",
        accentSoft: "rgb(var(--c-accent-soft) / <alpha-value>)",
        success: "rgb(var(--c-success) / <alpha-value>)",
        danger: "rgb(var(--c-danger) / <alpha-value>)",
        warn: "rgb(var(--c-warn) / <alpha-value>)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
