/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Ink wash. Source palette: #FFFFE3 #4A4A4A #CBCBCB #6D8196
        paper: '#FFFFE3',
        surface: '#FFFEF4',
        sunk: '#F4F4DA',
        ink: '#4A4A4A',
        'ink-soft': '#5E5E5E',
        muted: '#767676',
        rule: '#CBCBCB',
        'rule-soft': '#E2E2CE',
        slate: '#6D8196',
        'slate-deep': '#55677A',
        'slate-tint': '#EAEEF2',
        moss: '#5F7A5C',
        'moss-tint': '#EAF0E8',
        clay: '#9C5B4A',
        'clay-tint': '#F6E8E3',
      },
      fontFamily: {
        sans: ['"Instrument Sans"', 'system-ui', '-apple-system', 'sans-serif'],
      },
      borderRadius: {
        pill: '999px',
        card: '10px',
        field: '8px',
      },
      transitionTimingFunction: {
        spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      keyframes: {
        fadeSlideUp: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          from: { transform: 'translateX(-100%)' },
          to: { transform: 'translateX(100%)' },
        },
        springScale: {
          '0%': { transform: 'scale(0)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
      animation: {
        fadeSlideUp: 'fadeSlideUp 0.3s ease-out both',
        shimmer: 'shimmer 1.6s infinite',
        springScale: 'springScale 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) both',
      },
    },
  },
  plugins: [],
};
