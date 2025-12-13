import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#020617',
        foreground: '#e5e7eb',
        surface: '#0b1120',
        border: '#1f2933',
        primary: {
          DEFAULT: '#14b8a6',
          foreground: '#020617',
        },
        secondary: {
          DEFAULT: '#f59e0b',
          foreground: '#e5e7eb',
        },
        input: {
          DEFAULT: '#38bdf8',
        },
        test: {
          DEFAULT: '#ef4444',
        },
      },
      fontFamily: {
        sans: ['var(--font-noto-sans)', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};

export default config;
