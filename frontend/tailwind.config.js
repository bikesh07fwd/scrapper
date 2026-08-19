/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#09090B",
        surface: "#111113",
        elevated: "#18181B",
        borderDark: "#27272A",
      },
    },
  },
  plugins: [],
}
