/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  corePlugins: {
    container: false,
  },
  theme: {
    extend: {
      colors: {
        moeblue: '#2563eb',
        moeslate: '#0f172a',
        moebg: '#f8fafc',
      },
      boxShadow: {
        panel: '0 8px 24px rgba(15, 23, 42, 0.08)',
      },
    },
  },
  plugins: [],
};