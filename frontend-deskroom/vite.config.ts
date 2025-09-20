import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, '../static/deskroom'), // Flask 정적 경로로 바로 출력
    emptyOutDir: true,
    manifest: true,
  },
  base: '/static/deskroom/', // 번들 경로 기준
})
