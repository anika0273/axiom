/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      white: '#ffffff',
      black: '#000000',
      // Backgrounds
      deep: 'var(--color-bg-deep)',
      card: 'var(--color-bg-card)',
      elevated: 'var(--color-bg-elevated)',
      hover: 'var(--color-bg-hover)',
      // Borders
      subtle: 'var(--color-border-subtle)',
      active: 'var(--color-border-active)',
      // Accents
      blue: 'var(--color-accent-blue)',
      'blue-dim': 'var(--color-accent-blue-dim)',
      green: 'var(--color-accent-green)',
      amber: 'var(--color-accent-amber)',
      red: 'var(--color-accent-red)',
      // Text
      primary: 'var(--color-text-primary)',
      secondary: 'var(--color-text-secondary)',
      muted: 'var(--color-text-muted)',
      data: 'var(--color-text-data)',
    },
    extend: {
      fontFamily: {
        display: ['Syne', 'sans-serif'],
        mono: ['DM Mono', 'monospace'],
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
      },
      animation: {
        shimmer: 'shimmer 2s linear infinite',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      spacing: {
        sidebar: '240px',
      },
      maxWidth: {
        content: '1280px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)',
        elevated: '0 4px 12px rgba(0,0,0,0.5), 0 2px 4px rgba(0,0,0,0.3)',
        glow: '0 0 20px rgba(59,130,246,0.2)',
        'glow-lg': '0 0 30px rgba(59,130,246,0.35)',
      },
    },
  },
  plugins: [],
}
