/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./src/**/*.{js,jsx,ts,tsx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ['"Plus Jakarta Sans"', 'sans-serif'],
            },
            colors: {
                brand: {
                    50: '#eef2ff',
                    100: '#e0e7ff',
                    200: '#c7d2fe',
                    300: '#a5b4fc',
                    400: '#818cf8',
                    500: '#6366f1',
                    600: '#4f46e5', // Indigo-600
                    700: '#4338ca',
                    800: '#3730a3',
                    900: '#312e81',
                },
                accent: {
                    50: '#f0fdf4',
                    500: '#10b981', // Emerald-500
                    600: '#059669',
                }
            },
            animation: {
                'blob': 'blob 10s infinite',
                'fade-in': 'fadeIn 1.6s cubic-bezier(0.16, 1, 0.3, 1) forwards',
                'slide-up': 'slideUp 1.8s cubic-bezier(0.16, 1, 0.3, 1) forwards',
                'pulse-slow': 'pulse 3s infinite',
            },
            keyframes: {
                blob: {
                    '0%': { transform: 'translate(0px, 0px) scale(1)' },
                    '33%': { transform: 'translate(30px, -50px) scale(1.1)' },
                    '66%': { transform: 'translate(-20px, 20px) scale(0.9)' },
                    '100%': { transform: 'translate(0px, 0px) scale(1)' },
                },
                fadeIn: {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
                slideUp: {
                    '0%': { transform: 'translateY(40px)', opacity: '0' },
                    '100%': { transform: 'translateY(0)', opacity: '1' },
                }
            }
        }
    },
    plugins: [],
}
