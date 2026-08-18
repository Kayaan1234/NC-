import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

// Reuses the app's own Vite config rather than redeclaring one. That matters
// more than it looks: the MDX -> katex -> todo-cue -> shiki plugin chain in
// vite.config.ts is what makes `src/content/**/*.mdx` importable at all, and
// src/content/index.ts imports those files eagerly. Any test that transitively
// reaches it would fail to transform without the identical plugin array.
//
// The suite is deliberately pure-logic only — no DOM, no component rendering —
// so `environment` stays at the default 'node' and CSS is left untransformed.
// main.tsx pulls in katex's stylesheet and three @fontsource packages, none of
// which a logic test needs.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      include: ['src/**/*.test.ts'],
      environment: 'node',
      css: false,
      // Fail on an unhandled rejection rather than letting it pass silently —
      // several of these tests deliberately reject promises.
      dangerouslyIgnoreUnhandledErrors: false,
      restoreMocks: true,
      unstubEnvs: true,
      unstubGlobals: true,
    },
  }),
)
