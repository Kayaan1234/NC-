// The real Step0 C++, imported and syntax-highlighted at BUILD time.
//
// The walkthrough's code panel shows slices of these files, located by function
// signature (see content/walkthrough/anchors.ts). That is the whole point of the
// arrangement: the code on screen is the code that compiles and trains, so it cannot
// drift from the source the way a hand-pasted excerpt can. The old MDX pages had
// already drifted this way without anyone noticing, quoting a comment in
// binaryLoss() that the real file does not contain.
//
// `?highlight` is the local Vite plugin in ../../../vite-plugin-cpp-highlight.ts. It
// hands back the raw text (for slicing) and one HTML string per line (for
// rendering), with Shiki running at build time so no highlighter reaches the
// browser. Two things make importing from outside the Vite root work, and both are
// load-bearing:
//
//   - the plugin resolves the path against the importing module, since the default
//     resolver is scoped to the project root;
//   - the Dockerfile's build stage must copy backend/services/Step0/ alongside
//     frontend/ with the relative path preserved, or `npm run build` fails inside
//     the image while passing on a laptop. CI never runs a build, so only a real
//     `docker build` catches a regression there.

import type { SourceBundle } from '../walkthrough/types'

import { raw as mathRaw, lines as mathLines } from '../../../../backend/services/Step0/math.hpp?highlight'
import {
  raw as logisticRaw,
  lines as logisticLines,
} from '../../../../backend/services/Step0/logistic_regression.hpp?highlight'
import { raw as mainRaw, lines as mainLines } from '../../../../backend/services/Step0/main.cpp?highlight'

/** Raw text, for anchor extraction. */
export const STEP0_SOURCE = {
  'math.hpp': mathRaw,
  'logistic_regression.hpp': logisticRaw,
  'main.cpp': mainRaw,
} as const

/** Highlighted HTML, one entry per source line, index-aligned with STEP0_SOURCE. */
export const STEP0_HIGHLIGHTED: Record<SourceFile, string[]> = {
  'math.hpp': mathLines,
  'logistic_regression.hpp': logisticLines,
  'main.cpp': mainLines,
}

export type SourceFile = keyof typeof STEP0_SOURCE

/**
 * The two together, in the shape the rendering components take.
 *
 * Components receive this as a value rather than importing the two constants above,
 * so nothing that draws code is tied to step0. Adding a model means adding its own
 * source.ts and handing the bundle to the registry.
 */
export const STEP0_SOURCES: SourceBundle = {
  raw: STEP0_SOURCE,
  highlighted: STEP0_HIGHLIGHTED,
}
