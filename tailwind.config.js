/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./accounts/templates/**/*.html",
    "./bookings/templates/**/*.html",
    "./restaurants/templates/**/*.html",
    "./static/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        seated: {
          bg: "#EAE6DF",
          ink: "#0D0F14",
          "ink-mid": "#2A2D38",
          "ink-light": "#6B6E7A",
          blue: "#1B3A6B",
          "blue-mid": "#2952A3",
          "blue-light": "#4A72C4",
          "blue-pale": "#EBF0FA",
          paper: "#FFFFFF",
          "paper-warm": "#FAFAF6",
          cream: "#F5F1EA",
          rule: "#E0DBD2",
          "rule-dark": "#C8C2B6",
        },
      },
      fontFamily: {
        mono: ['"Space Mono"', "monospace"],
        serif: ['"Libre Baskerville"', "serif"],
      },
      maxWidth: {
        content: "680px",
        auth: "420px",
        signup: "36rem",
      },
      letterSpacing: {
        store: "0.24em",
        section: "0.22em",
        navlink: "0.1em",
      },
    },
  },
  plugins: [],
};
