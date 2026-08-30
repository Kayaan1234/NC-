// Schema for a model's authored "learn" flow: the explanation a user reads before
// training. Content is authored by hand under content/<modelId>/ and registered in
// content/index.ts — see content/README.md for the workflow.
//
// There are two shapes, and a model picks one:
//
//   'pages'       a sequence of .mdx pages, one per source file, with prev/next
//                 pagination. Both models started here, and it is still the right
//                 first draft: prose is far quicker to write than a timeline.
//   'walkthrough' one continuous narrated timeline the reader plays and scrubs,
//                 with the rail as chapters. Both step0 and step1 are this now.
//
// A discriminated union rather than optional fields, because the two genuinely have
// different content: a page carries a Body component, a chapter carries a slug and a
// span of scenes. An optional-field version would have to make LearnSection.Body
// optional and encode "exactly one of these is populated" as an invariant nothing
// checks. The union costs one narrowing, in Learn.tsx: `.sections` is read nowhere
// else, and the other two call sites read `name` (Bridge.tsx) or just ask whether
// content exists (Training.tsx), both of which work on the union directly.
//
// Nothing here fetches from the backend. A learn flow's display name and its prose
// both come from the authored content, so reading works for any logged-in user,
// verified or not.

import type { ComponentType } from 'react'

import type { Abstraction } from './abstraction/types'
import type { Chapter, Scene, SourceBundle, StageState } from './walkthrough/types'

// One page of a paged flow. The first section of every model is the overview; each
// subsequent section corresponds to one source file.
export interface LearnSection {
  slug: string // URL segment, e.g. 'overview', 'logistic_regression'
  title: string // display title, e.g. 'Overview', 'logistic_regression.hpp'
  Body: ComponentType // default export of the section's .mdx file
}

interface ModelContentBase {
  // Display name for the flow. Restates the backend registry `name` on purpose —
  // learn pages are static and make no API call — so keep the two in sync by hand.
  name: string
  // The model's real C++, imported and highlighted at build time. Anything that
  // draws code takes this as a value, so no rendering component is tied to one
  // model. Optional because a model can have prose with no code panels.
  sources?: SourceBundle
  // An optional closing page, reached from the rail after the main flow. It sits on
  // the BASE rather than on one variant because both shapes want one: step0 is a
  // walkthrough and step1 is pages, and the Python comparison is worth having on
  // either. See content/abstraction/types.ts.
  epilogue?: Epilogue
}

/**
 * The closing page of a model's learn flow: the same model expressed at four levels
 * of abstraction, with the defaults each library filled in on the reader's behalf.
 *
 * `slug` is a URL segment alongside the chapter/section slugs, so keep it stable and
 * distinct from them.
 */
export interface Epilogue {
  slug: string
  title: string
  abstraction: Abstraction
  // The compiled MDX carrying this page's Python and NumPy snippets, one <Snippet>
  // per authored cell. Code lives in MDX so the existing build-time shiki pass
  // highlights it, the same reason narration lives there for KaTeX.
  Snippets: ComponentType
}

export interface PagedContent extends ModelContentBase {
  kind: 'pages'
  // Ordered: overview first, then one section per source file. Pagination,
  // prev/next, the table of contents and the position indicator are all derived
  // from this array, so ordering here is the only place page order is declared.
  sections: LearnSection[]
}

export interface WalkthroughContent extends ModelContentBase {
  kind: 'walkthrough'
  // Rail entries and seek targets. `slug` is the URL segment, and keeping the
  // slugs a model's pages used means old /learn/:slug links still resolve.
  chapters: Chapter[]
  // Ordered. Durations are summed to derive every start time, so this array is the
  // only place the running order is declared.
  //
  // Stored erased to StageState: the player places scenes on a clock and hands each
  // one's stage back to the model's own Stage component, and neither job needs to
  // know the variants. Build one of these with `walkthrough()` below rather than by
  // hand, which is what keeps the erasure honest.
  scenes: Scene<StageState>[]
  // What the top half of the player draws. Per-model by nature: choosing which
  // diagram a stage means is the one part of a walkthrough that cannot be generic.
  Stage: ComponentType<{ stage: StageState; progress: number }>
  // The compiled narration MDX: every <Beat> for this walkthrough, rendered whole
  // and filtered by the active beat. See components/walkthrough/Beat.tsx.
  Narration: ComponentType
}

/**
 * Build a walkthrough entry, tying a model's scenes to the component that draws them.
 *
 * This exists for the same reason `sources` is a value rather than an import: an
 * earlier version typed `scenes` as step0's own scene type and had the player import
 * step0's Stage by name, which quietly made the whole player step0-only.
 *
 * `S` is inferred from BOTH `scenes` and `Stage`, so handing step1's scenes to
 * step0's Stage fails here at the call site rather than rendering the wrong picture.
 * That inference is the entire point of the function; the single cast below is only
 * sound because of it. React checks props contravariantly, so a component that draws
 * one model's stages is genuinely not a component that draws any model's stages. What
 * makes the cast safe is narrower and worth stating: the player only ever passes a
 * stage it read out of `scenes`, and every one of those is an `S` by this signature.
 */
export function walkthrough<S extends StageState>(content: {
  name: string
  chapters: Chapter[]
  scenes: Scene<S>[]
  Stage: ComponentType<{ stage: S; progress: number }>
  Narration: ComponentType
  sources?: SourceBundle
  epilogue?: Epilogue
}): WalkthroughContent {
  return {
    kind: 'walkthrough',
    ...content,
    Stage: content.Stage as ComponentType<{ stage: StageState; progress: number }>,
  }
}

export type ModelContent = PagedContent | WalkthroughContent
