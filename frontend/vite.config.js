import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

const devApiTarget = process.env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8080';

export default defineConfig({
  plugins: [vue()],
  base: '/static/',
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: devApiTarget,
        changeOrigin: true,
      },
    },
  },
});