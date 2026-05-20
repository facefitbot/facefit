import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        milk: "#fbf7f2",
        pearl: "#f2e7de",
        rose: "#be7d86",
        clay: "#9d7067",
        ink: "#3e3631",
        sage: "#7b967c"
      },
      boxShadow: {
        soft: "0 18px 50px rgba(63, 52, 46, 0.10)"
      },
      borderRadius: {
        card: "8px"
      }
    }
  },
  plugins: []
} satisfies Config;

