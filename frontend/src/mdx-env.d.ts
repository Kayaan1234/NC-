// Lets TypeScript accept `import Page from './x.mdx'`. tsconfig sets an explicit
// `types` array, so @types/mdx would not be auto-loaded; this local ambient
// declaration is the reliable route and adds no dependency. The MDX Vite plugin
// (see vite.config.ts) does the actual compilation; a page's default export is a
// React component that renders its prose + fenced code as plain HTML.
declare module '*.mdx' {
  import type { ComponentType } from 'react'
  const MDXComponent: ComponentType
  export default MDXComponent
}
