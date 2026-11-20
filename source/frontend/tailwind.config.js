/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      keyframes: { talk: { "0%": { height: "4px" }, "100%": { height: "14px" } } },
      animation: { talk: "talk 0.25s ease-in-out infinite alternate" },
      fontFamily: { sans: ["Inter", "Segoe UI Variable", "Segoe UI", "system-ui", "sans-serif"], serif: ["Georgia", "Cambria", "serif"] },
      colors: {
        ink: { 50: "#f6f7f9", 100: "#eceef2", 200: "#d5d9e2", 400: "#8a93a6", 600: "#4b5468", 800: "#232838", 900: "#151925", 950: "#0d1018" },
        brand: { 50: "#eef5ff", 100: "#d9e8ff", 400: "#5b8def", 500: "#3a6fe0", 600: "#2754c4", 700: "#1f43a0" },
        gold: { 400: "#d9b45a", 500: "#c39a3a" },
      },
    },
  },
  plugins: [],
};
