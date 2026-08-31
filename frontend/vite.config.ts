import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import mdx from '@mdx-js/rollup'
import rehypeShiki from '@shikijs/rehype'
import rehypeKatex from 'rehype-katex'
import remarkMath from 'remark-math'
import rehypeTodoCue from './src/content/rehype-todo-cue'
import cppHighlight from './vite-plugin-cpp-highlight'
import { ncDark } from './src/styles/shiki-theme'

// Single-origin dev: the SPA is served from :5173 and calls the API with
// relative paths, with Vite forwarding the backend's route prefixes to uvicorn.
// This is load-bearing, not convenience — the refresh cookie is SameSite=Strict,
// so it only rides requests the browser considers same-site. Same-origin dev also
// sidesteps CORS entirely and dodges the IPv4/IPv6 loopback split: Vite listens on
// IPv6 (::1) while uvicorn listens on IPv4 (127.0.0.1), so a browser resolving
// `localhost` to ::1 first could never reach a direct http://localhost:8000 call.
//
// The proxy target is 127.0.0.1, NOT `localhost`: Node 17+ resolves `localhost`
// to ::1 first, where uvicorn isn't listening, so `localhost` would fail here too.
const BACKEND = process.env.VITE_DEV_BACKEND ?? 'http://127.0.0.1:8000'

export default defineConfig({
  // MDX powers the authored "learn" pages (src/content/**/*.mdx). The plugin must
  // run before @vitejs/plugin-react, and react() is told to also transform .mdx so
  // Fast Refresh works on the compiled pages.
  //
  // Both the highlighter and the math renderer run HERE, at build time: no syntax
  // highlighting or LaTeX library is shipped to the browser, and KaTeX's fonts come
  // out of the npm package rather than a CDN — the privacy policy states there are
  // no third-party scripts, so nothing in this app may fetch off-origin.
  plugins: [
    // The step0 walkthrough shows the real Step0 C++, imported from outside this
    // root with `?highlight` and syntax-highlighted here rather than in the browser,
    // for the same build-time reason the MDX pipeline below highlights its fences.
    cppHighlight(),
    {
      enforce: 'pre',
      ...mdx({
        remarkPlugins: [remarkMath],
        rehypePlugins: [
          rehypeKatex,
          // Before rehypeShiki, so a ```todo authoring cue is lifted out of the
          // tree and never syntax-highlighted as if it were code.
          rehypeTodoCue,
          [
            rehypeShiki,
            {
              theme: ncDark,
              // An authoring typo in a fence must never be able to fail a
              // production build: an unknown language degrades to plain text.
              fallbackLanguage: 'text',
              defaultLanguage: 'text',
            },
          ],
        ],
      }),
    },
    react({ include: /\.(jsx|js|mdx|md|tsx|ts)$/ }),
  ],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '^/(auth|users|train|bridge|health|scalar|openapi\\.json)($|/)': {
        target: BACKEND,
        changeOrigin: false,
      },
    },
  },
})
