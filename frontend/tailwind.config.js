/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        accent: {
          purple: '#7c3aed',
          blue: '#0ea5e9',
          teal: '#14b8a6',
        },
        glass: {
          white: 'rgba(255, 255, 255, 0.06)',
          'white-strong': 'rgba(255, 255, 255, 0.10)',
          border: 'rgba(255, 255, 255, 0.12)',
        },
      },
      backdropBlur: {
        glass: '24px',
        'glass-strong': '40px',
      },
      borderRadius: {
        pill: '50px',
        glass: '20px',
        'glass-lg': '24px',
      },
      transitionTimingFunction: {
        spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      keyframes: {
        float: {
          '0%': { transform: 'translate(0, 0) scale(1)' },
          '100%': { transform: 'translate(60px, 40px) scale(1.1)' },
        },
        fadeSlideUp: {
          from: { opacity: '0', transform: 'translateY(12px)' },
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
        float: 'float 26s ease-in-out infinite alternate',
        fadeSlideUp: 'fadeSlideUp 0.3s ease-out both',
        shimmer: 'shimmer 1.6s infinite',
        springScale: 'springScale 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) both',
      },
    },
  },
  plugins: [],
};
