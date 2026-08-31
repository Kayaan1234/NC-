import { createContext, useContext, type ReactNode } from 'react'

// One authored code snippet from a model's abstraction ladder.
//
// Same trick as components/walkthrough/Beat.tsx: the MDX document is compiled once
// and rendered whole, and every snippet except the requested one returns null. The
// difference is that this page needs four snippets in four different places on
// screen at the same time, so the MDX is rendered once per cell with a different id
// asked for each time.
//
// That sounds wasteful and is not: only the active concept is mounted, the document
// is a few hundred nodes, and the alternative is a slot registry that has to track
// mounting order. Reusing a component that already works beats inventing one.
//
// A null activeId renders nothing rather than everything, which is the opposite of
// Beat's default. Beat's fallback is a readable document; here a missing id means a
// cell asked for a snippet that does not exist, and quietly dumping all fifteen into
// one card would hide that. The test catches it first either way.

const SnippetContext = createContext<string | null>(null)

export const SnippetProvider = SnippetContext.Provider

export default function Snippet({ id, children }: { id: string; children: ReactNode }) {
  const activeId = useContext(SnippetContext)
  if (id !== activeId) return null
  return <div data-snippet={id}>{children}</div>
}
