/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          blue: '#1a6dba',
          hover: '#155da0',
          dark: '#0f1e30',
          light: '#f0f4fa',
          glow: 'rgba(26, 109, 186, 0.35)',
        },
        status: {
          success: '#2a9d5c',
          warning: '#e07a10',
          danger: '#e63946',
        }
      },
      fontFamily: {
        sans: ['Barlow', 'sans-serif'],
        condensed: ['Barlow Condensed', 'sans-serif'],
      },
      boxShadow: {
        'glow-sm': '0 0 0 3px rgba(26, 109, 186, 0.15)',
        'glow-md': '0 0 12px rgba(26, 109, 186, 0.35)',
        'glow-lg': '0 0 20px rgba(26, 109, 186, 0.45)',
        'card-hover': '0 4px 20px -4px rgba(26, 109, 186, 0.25)',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-in-out',
        'pulse-slow': 'pulseObstaculo 1.6s ease-in-out infinite',
        'slide-in': 'slideIn 0.35s ease-out',
        'icon-pulse': 'iconPulse 2.2s ease-in-out infinite',
        'shimmer': 'shimmer 1.4s linear infinite',
        'progress-glow': 'progressGlow 1.8s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        pulseObstaculo: {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '0.85' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        iconPulse: {
          '0%, 100%': { filter: 'drop-shadow(0 0 0px rgba(26,109,186,0.6))' },
          '50%': { filter: 'drop-shadow(0 0 6px rgba(26,109,186,0.9))' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        progressGlow: {
          '0%, 100%': { boxShadow: '0 0 4px rgba(26,109,186,0.4)' },
          '50%': { boxShadow: '0 0 10px rgba(26,109,186,0.8)' },
        }
      }
    },
  },
  plugins: [],
}