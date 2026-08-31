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

// C++ imported with `?highlight`, served by the local plugin in
// vite-plugin-cpp-highlight.ts. `raw` is the file verbatim, for slicing a function
// out of it by signature; `lines` is the same file syntax-highlighted at build time,
// one HTML string per line, index-aligned with `raw.split('\n')`.
//
// Vite's own client types declare `*?raw` but nothing declares a custom query, so
// this one has to be written out. It is the same reason `*.mdx` above needs a
// declaration: the plugin does the work, TypeScript just needs telling the shape.
declare module '*?highlight' {
  export const raw: string
  export const lines: string[]
}
