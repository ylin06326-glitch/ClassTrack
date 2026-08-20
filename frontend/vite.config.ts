import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // 开发模式下将 /api 代理到 FastAPI 后端
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 构建产物由 FastAPI 托管,无需 hash 也能保证缓存刷新(每次打包全量覆盖)
    outDir: 'dist',
    chunkSizeWarningLimit: 1500,
  },
})
