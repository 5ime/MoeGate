import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const devApiTarget = process.env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8080';
const __dirname = path.dirname(fileURLToPath(import.meta.url));

function moegateBuildInfoPlugin() {
  return {
    name: 'moegate-build-info',
    closeBundle() {
      const pkgPath = path.resolve(__dirname, 'package.json');
      let version = '0.0.0';
      try {
        version = JSON.parse(fs.readFileSync(pkgPath, 'utf-8')).version || version;
      } catch {
        // ignore
      }
      const info = {
        app: 'moegate-webui',
        version,
        built_at: new Date().toISOString(),
      };
      fs.writeFileSync(
        path.resolve(__dirname, '../static/.moegate-build.json'),
        `${JSON.stringify(info, null, 2)}\n`,
        'utf-8',
      );
    },
  };
}

export default defineConfig({
  plugins: [vue(), moegateBuildInfoPlugin()],
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