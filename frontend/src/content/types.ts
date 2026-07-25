// Schema for a model's authored "learn" flow: the explanation pages a user reads
// before training. Content is authored by hand (MDX under content/<modelId>/) and
// registered in content/index.ts — see content/README.md for the workflow.
//
// Nothing here fetches from the backend: a learn page's display name and its prose
// both come from the authored content, so reading works for any logged-in user,
// verified or not.

import type { ComponentType } from 'react'

// One page of the flow. The first section of every model is the overview; each
// subsequent section corresponds to one source file.
export interface LearnSection {
  slug: string // URL segment, e.g. 'overview', 'logistic_regression'
  title: string // display title, e.g. 'Overview', 'logistic_regression.hpp'
  Body: ComponentType // default export of the section's .mdx file
}

export interface ModelContent {
  // Display name for the flow. Restates the backend registry `name` on purpose —
  // learn pages are static and make no API call — so keep the two in sync by hand.
  name: string
  // Ordered: overview first, then one section per source file. Pagination,
  // prev/next, the table of contents and the position indicator are all derived
  // from this array, so ordering here is the only place page order is declared.
  sections: LearnSection[]
}
