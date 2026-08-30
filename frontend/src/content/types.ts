// Schema for a model's authored "learn" flow: the explanation a user reads before
// training. Content is authored by hand under content/<modelId>/ and registered in
// content/index.ts — see content/README.md for the workflow.
//
// There are two shapes, and a model picks one:
//
//   'pages'       a sequence of .mdx pages, one per source file, with prev/next
//                 pagination. This is how step1 is written.
//   'walkthrough' one continuous narrated timeline the reader plays and scrubs,
//                 with the rail as chapters. This is how step0 is written.
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

import type { Chapter, SourceBundle } from './walkthrough/types'
import type { Step0Scene } from './step0/walkthrough'

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
  scenes: Step0Scene[]
  // The compiled narration MDX: every <Beat> for this walkthrough, rendered whole
  // and filtered by the active beat. See components/walkthrough/Beat.tsx.
  Narration: ComponentType
}

export type ModelContent = PagedContent | WalkthroughContent
