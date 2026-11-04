/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0d12",
        panel: "#12151c",
        raised: "#181c25",
        line: "#262b36",
        ink: "#e7e9ee",
        muted: "#a2a9b6",
        faint: "#7f8794",
        halo: "#f0c05a",
        pass: "#3ecf8e",
        fail: "#f2555a",
        warn: "#e8a33d",
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        halo: "0 0 24px -6px rgba(240, 192, 90, 0.45)",
      },
    },
  },
  plugins: [],
};
