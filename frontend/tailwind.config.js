/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Two-tone greyscale. Source: #4A4A4A and #CBCBCB.
        // #CBCBCB is ~1.7:1 on white, so it is a border value only, never text.
        // Everything between is derived from the same neutral.
        paper: '#FFFFFF',
        surface: '#FAFAFA',
        sunk: '#F2F2F2',
        ink: '#4A4A4A',
        'ink-soft': '#6A6A6A',
        muted: '#757575',
        rule: '#CBCBCB',
        'rule-soft': '#E5E5E5',
        'rule-strong': '#A8A8A8',
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
