import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // ── Dynamic Theme Surfaces (per CSS variables) ──
        background: "var(--bg-page)",
        card: "var(--bg-surface)",
        surface: {
          DEFAULT: "var(--bg-surface)",
          secondary: "var(--bg-surface-secondary)",
          elevated: "var(--bg-surface-elevated)",
        },
        border: "var(--border-color)",
        "border-strong": "var(--border-strong)",

        // ── Text hierarchy ──
        content: {
          DEFAULT: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
        },

        // ── Actions & semantics ──
        primary: {
          DEFAULT: "#4f46e5",
          hover: "#4338ca",
          light: "#818cf8",
        },
        success: {
          DEFAULT: "#10b981",
          light: "#34d399",
        },
        warning: {
          DEFAULT: "#f59e0b",
          light: "#fbbf24",
        },
        danger: {
          DEFAULT: "#ef4444",
          light: "#f87171",
        },
        info: {
          DEFAULT: "#06b6d4",
          light: "#22d3ee",
        },
        ai: {
          DEFAULT: "#8b5cf6",
          light: "#a78bfa",
        },
      },
      fontSize: {
        // Financial / dashboard type scale
        "kpi": ["1.75rem", { lineHeight: "2rem", fontWeight: "700" }],
        "amount-lg": ["1.125rem", { lineHeight: "1.5rem", fontWeight: "700" }],
        "amount": ["0.9375rem", { lineHeight: "1.25rem", fontWeight: "600" }],
        "table-head": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.05em" }],
      },
      spacing: {
        // consistent scale reinforcement (Tailwind already covers most)
        "18": "4.5rem",
      },
      borderRadius: {
        card: "0.75rem",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "modal-in": {
          "0%": { opacity: "0", transform: "translateY(8px) scale(0.98)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        "shimmer": {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.2s ease-out",
        "modal-in": "modal-in 0.18s ease-out",
        "shimmer": "shimmer 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
