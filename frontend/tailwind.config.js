/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cat: {
          yellow: '#FFCD11',
          black: '#111111',
          dark: '#1C1C1E',
          gray: '#2C2C2E',
        }
      }
    },
  },
  plugins: [],
};
