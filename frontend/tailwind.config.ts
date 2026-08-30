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
        background: "#0b0f19",
        card: "#111827",
        border: "#1f2937",
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
        }
      },
    },
  },
  plugins: [],
};
export default config;
