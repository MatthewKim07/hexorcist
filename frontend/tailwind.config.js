/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // The bench the instrument sits on, a shade under the faceplate
        bench: "#D8DBD5",
        // Faceplate
        bg: "#E3E5E0",
        raised: "#EEF0EC",
        line: "#C4C8C1",
        ink: "#202427",
        muted: "#5A615D",
        pass: "#1E6B43",
        fail: "#B0382F",
        probe: "#1C6884",
        // The one lit screen
        screen: {
          DEFAULT: "#121816",
          raised: "#1A221F",
          line: "#2A3430",
          ink: "#C9D1CC",
          muted: "#8A958F",
        },
        trace: "#E8C15A",
        "pass-lit": "#5CC98A",
        "fail-lit": "#F0766B",
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
