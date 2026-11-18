/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: v("bg"), bg2: v("bg2"), card: v("card"), forest: v("forest"), olive: v("olive"), gold: v("gold"),
        walnut: v("walnut"), ink: v("ink"), muted: v("muted"), line: v("line"), danger: v("danger"), success: v("success"),
        onforest: v("onforest"),
      },
      fontFamily: {
        serif: ['"Cormorant Garamond"', "Garamond", "Georgia", "serif"],
        sans: ['"DM Sans"', "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgb(var(--shadow) / 0.06), 0 8px 24px -12px rgb(var(--shadow) / 0.18)",
        lift: "0 2px 4px rgb(var(--shadow) / 0.08), 0 18px 40px -18px rgb(var(--shadow) / 0.35)",
      },
      letterSpacing: { eyebrow: "0.22em" },
    },
  },
  plugins: [],
};
