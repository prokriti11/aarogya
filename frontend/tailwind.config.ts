import type { Config } from "tailwindcss";

// Clinical-chart palette: cool chart paper, deep teal ink, vitals colors for outcomes.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F4F7F6",
        sheet: "#FFFFFF",
        ink: { DEFAULT: "#123A36", soft: "#4A6662", faint: "#86A09C" },
        rule: "#D3DEDB",
        pass: { DEFAULT: "#0E7C6B", tint: "#DDF1EC" },
        fail: { DEFAULT: "#B4332A", tint: "#F8E1DE" },
        watch: { DEFAULT: "#B7791F", tint: "#FBEED6" },
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
      },
      fontSize: {
        // modular scale, ratio ~1.25
        xs: ["0.8rem", "1.15rem"], sm: ["0.875rem", "1.3rem"], base: ["1rem", "1.55rem"],
        lg: ["1.25rem", "1.7rem"], xl: ["1.563rem", "1.9rem"], "2xl": ["1.953rem", "2.2rem"],
        "3xl": ["2.441rem", "2.6rem"], "4xl": ["3.052rem", "3.1rem"], "5xl": ["3.815rem", "3.8rem"],
      },
    },
  },
  plugins: [],
};
export default config;
