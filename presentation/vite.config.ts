import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The deck reads its numbers from ../data, so the dev server must be allowed
// to serve files one level above this folder.
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    port: 5180,
    strictPort: true,
    fs: { allow: ['..'] },
  },
  preview: { port: 5181, strictPort: true },
})
