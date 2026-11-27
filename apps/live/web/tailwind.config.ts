import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: "#0A0C14",
          card: "#12151E",
          elevated: "#1A1D2E",
        },
        accent: {
          blue: "#4F8EF7",
          gold: "#F5C842",
          green: "#3DCC7E",
          red: "#E05252",
          purple: "#9B72CF",
          pink: "#E8629A",
        },
        btext: {
          primary: "#FFFFFF",
          secondary: "#A0A8C0",
          muted: "#5A607A",
        },
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
      },
      animation: {
        fadeUp: "fadeUp 0.4s ease both",
        creditPulse: "creditPulse 1.4s ease infinite",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        creditPulse: {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
