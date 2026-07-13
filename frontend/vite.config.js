import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Solo dev: el backend FastAPI corre en el 8000 y sirve /api.
  // En produccion el propio FastAPI sirve el build, asi que no afecta.
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
