import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Single-origin dev, mirroring the production nginx proxy
// (docker/nginx.conf.template): the SPA is served from :5173 and calls the API
// with relative paths (VITE_API_URL="" in .env), and Vite forwards the backend's
// route prefixes to uvicorn. Keeping dev same-origin sidesteps CORS entirely, the
// SameSite=Strict refresh cookie stays same-site, and — the actual bug this fixes
// — it dodges the IPv4/IPv6 loopback split: Vite listens on IPv6 (::1) while
// uvicorn listens on IPv4 (127.0.0.1), so a browser resolving `localhost` to ::1
// first could never reach a direct http://localhost:8000 API call.
//
// The proxy target is 127.0.0.1, NOT `localhost`: Node 17+ resolves `localhost`
// to ::1 first, where uvicorn isn't listening, so `localhost` would fail here too.
const BACKEND = process.env.VITE_DEV_BACKEND ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // The backend's surface, matching nginx's `^/(auth|users|rungs|health|scalar)`.
      // openapi.json is added so the /scalar API docs also load in dev.
      '^/(auth|users|rungs|health|scalar|openapi\\.json)($|/)': {
        target: BACKEND,
        changeOrigin: false,
      },
    },
  },
})
