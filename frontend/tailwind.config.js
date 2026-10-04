/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Noto Serif SC"', '"Songti SC"', "ui-serif", "serif"],
      },
      colors: {
        parchment: "#f5ecd6",
        ink: "#2a1f14",
      },
      boxShadow: {
        page: "inset 0 0 60px rgba(80,55,20,0.18)",
      },
    },
  },
  plugins: [],
};
