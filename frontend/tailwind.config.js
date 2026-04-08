/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 60-30-10 Color System
        // Dominant (60%)
        dominant: {
          DEFAULT: '#01000F',
          light: '#0A0A1A',
          white: '#FFFFFF',
        },
        // Secondary (30%)
        secondary: {
          DEFAULT: '#FFFFFF',
          light: '#E2E8F0',
          lighter: '#F1F5F9',
        },
        // Glassmorphism variants
        glass: {
          DEFAULT: 'rgba(255, 255, 255, 0.05)',
          hover: 'rgba(255, 255, 255, 0.1)',
        },
        // Accent (10%)
        accent: {
          DEFAULT: '#00E5FF',
          hover: '#00B8CC',
          success: '#16A34A',
          error: '#DC2626',
        },
        // Keep standard names for shadcn/ui and tailwind defaults if needed
        slate: {
          900: '#0F172A',
          500: '#64748B',
          200: '#E2E8F0',
          100: '#F1F5F9',
          50: '#F8FAFC',
        },
        sky: {
          500: '#0EA5E9',
          600: '#0284C7',
        },
      },
      fontFamily: {
        heading: ['Archivo', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'neon': '0 0 15px rgba(0, 229, 255, 0.5)',
        'neon-hover': '0 0 25px rgba(0, 229, 255, 0.8)',
      },
    },
  },
  plugins: [],
}
