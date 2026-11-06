/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0b0d",
        panel: "#0b0b0d",
        raised: "#151518",
        line: "#232327",
        ink: "#ececee",
        muted: "#a0a0a8",
        faint: "#80808a",
        accent: "#8b9bff",
        pass: "#3fb97f",
        fail: "#ef5b5b",
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
