/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        raised: "var(--raised)",
        line: "var(--line)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        pass: "var(--pass)",
        fail: "var(--fail)",
        running: "var(--running)",
        queued: "var(--queued)",
        brand: "var(--brand)",
        probe: "#1C6884",
        // Lit board (unchanged for existing pages)
        screen: {
          DEFAULT: "#121816",
          raised: "#1A221F",
          line: "#2A3430",
          ink: "#C9D1CC",
          muted: "#8A958F",
        },
        trace: "var(--brand)",
        "pass-lit": "#5CC98A",
        "fail-lit": "#F0766B",
      },
      borderRadius: {
        card: "var(--radius)",
      },
      fontFamily: {
        sans: ['"Geist Sans"', "system-ui", "sans-serif"],
        mono: ['"Geist Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        xs: ["12px", "16px"],
        sm: ["14px", "20px"],
        base: ["16px", "24px"],
        lg: ["20px", "26px"],
        xl: ["28px", "34px"],
      },
      transitionTimingFunction: {
        out: "cubic-bezier(0.23, 1, 0.32, 1)",
        "in-out": "cubic-bezier(0.77, 0, 0.175, 1)",
      },
    },
  },
  plugins: [],
};
