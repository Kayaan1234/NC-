// The real Step1 C++, imported and syntax-highlighted at BUILD time.
//
// Same arrangement as step0/source.ts, and for the same reason: the code the
// walkthrough puts on screen is the code that compiles and trains, sliced out by
// function signature rather than pasted, so it cannot drift. See that file's header
// for how `?highlight` works and why the Dockerfile has to copy these sources into
// the frontend build stage.
//
// Five files instead of three, and one of them is large. main.cpp is 558 lines,
// most of them argument parsing the walkthrough never shows, but the import is
// whole-file: slices are computed from it at runtime. Two of its functions are worth
// the weight. `apply_defaults` is every default the reader will hit on the training
// page, in nine lines, and `train_mlp` is the entire training loop including the
// shuffle, the batching and the absorbed softmax gradient.
//
// One difference from Step0 that bit, and is now handled in anchors.ts: main.cpp
// declares its functions in a block at the top and defines them hundreds of lines
// below. `extractAnchor` skips declarations, so an anchor still finds the body.

import type { SourceBundle } from '../walkthrough/types'

import {
  raw as matrixRaw,
  lines as matrixLines,
} from '../../../../backend/services/Step1/matrix.hpp?highlight'
import { raw as mathRaw, lines as mathLines } from '../../../../backend/services/Step1/math.hpp?highlight'
import {
  raw as layerRaw,
  lines as layerLines,
} from '../../../../backend/services/Step1/layer.hpp?highlight'
import { raw as mlpRaw, lines as mlpLines } from '../../../../backend/services/Step1/MLP.hpp?highlight'
import { raw as mainRaw, lines as mainLines } from '../../../../backend/services/Step1/main.cpp?highlight'

/** Raw text, for anchor extraction. */
export const STEP1_SOURCE = {
  'matrix.hpp': matrixRaw,
  'math.hpp': mathRaw,
  'layer.hpp': layerRaw,
  'MLP.hpp': mlpRaw,
  'main.cpp': mainRaw,
} as const

/** Highlighted HTML, one entry per source line, index-aligned with STEP1_SOURCE. */
export const STEP1_HIGHLIGHTED: Record<Step1SourceFile, string[]> = {
  'matrix.hpp': matrixLines,
  'math.hpp': mathLines,
  'layer.hpp': layerLines,
  'MLP.hpp': mlpLines,
  'main.cpp': mainLines,
}

export type Step1SourceFile = keyof typeof STEP1_SOURCE

/** The two together, in the shape the rendering components take. */
export const STEP1_SOURCES: SourceBundle = {
  raw: STEP1_SOURCE,
  highlighted: STEP1_HIGHLIGHTED,
}
