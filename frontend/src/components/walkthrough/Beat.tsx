import { createContext, useContext, type ReactNode } from 'react'

import type { NarrationMode } from '../../content/walkthrough/types'

// One block of narration, keyed to a scene.
//
// This small component is what makes the "Read as text" view generated rather than
// maintained beside the animation. The narration MDX is compiled once and rendered
// whole; in 'play' mode every Beat except the active one returns null, and in 'text'
// mode they all render in document order. There is exactly one copy of the words,
// which is the only reason deleting the old prose pages is safe.
//
// `extrasFor` is how the text view gets a beat's picture and code to sit with its
// prose. Those live in the scene manifest rather than in the MDX, so the Beat cannot
// know about them; it asks the provider, which does. Keeping the lookup in a
// callback is what stops this file from having to import step0's manifest and become
// step0-specific.
//
// The default context is 'text' with no extras, on purpose. If narration.mdx is ever
// rendered without a provider, it shows all the prose rather than silently showing
// nothing.

interface NarrationState {
  mode: NarrationMode
  activeId: string | null
  extrasFor?: (id: string) => ReactNode
}

const NarrationContext = createContext<NarrationState>({ mode: 'text', activeId: null })

export const NarrationProvider = NarrationContext.Provider

export default function Beat({ id, children }: { id: string; children: ReactNode }) {
  const { mode, activeId, extrasFor } = useContext(NarrationContext)

  if (mode === 'play') {
    if (id !== activeId) return null
    // In the player the stage and code panel are laid out around the caption by
    // the player itself, so a beat renders its words and nothing else.
    return (
      <div className="beat" data-beat={id}>
        {children}
      </div>
    )
  }

  return (
    <div className="beat beat--text" data-beat={id}>
      {children}
      {extrasFor?.(id)}
    </div>
  )
}
