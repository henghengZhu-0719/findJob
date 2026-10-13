import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // 开发时把 /api 转发给本地 FastAPI，避免跨域；端口跟随 start.sh 的 PORT
    proxy: {
      '/api': { target: `http://127.0.0.1:${process.env.API_PORT || 8000}`, changeOrigin: true },
    },
  },
  // 构建产物直接交给 FastAPI 托管
  build: { outDir: '../static', emptyOutDir: true },
})
