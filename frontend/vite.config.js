import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],

  server: {
    port: 1232,
    strictPort: true,   // error claro si 1232 está ocupado (evita CORS por puerto inesperado)
    host: '127.0.0.1',
    hmr: false,
  },
});
