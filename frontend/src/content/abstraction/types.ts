// The abstraction ladder: one model expressed at four levels, and what each level
// decided without being asked.
//
// The page this describes closes the loop the walkthrough opens. The walkthrough
// goes maths -> C++. This goes library call -> C++, and its argument is that the
// one-liner is not the same computation as the C++ at all: sklearn defaults to
// lbfgs, a quasi-Newton method, where the reader hand-derived gradient descent, and
// to an L2 penalty, so it is not even minimising the same objective.
//
// The layout is CONCEPT-major, and that is a scaling decision rather than a
// stylistic one. Rung-major (pick a library, see its whole implementation) works for
// step0, where every rung fits on a screen. At step1 the C++ rung would be
// matrix.hpp + layer.hpp + MLP.hpp all at once. Concept-major asks "how does each
// rung initialise weights", and every cell stays short no matter how large the model
// is, because a cell only ever holds one concept's slice. Adding a model means
// adding concepts and anchors; it never means touching a component.

import type { CodeRef } from '../walkthrough/types'

/**
 * Where a rung's claims come from, and whether this repo can check them.
 *
 * This distinction is structural rather than a comment because the two really are
 * different. scikit-learn and numpy are pinned in
 * backend/requirements-worker.lock.txt, so a test can assert the version a claim was
 * made against is still the version the repo installs. PyTorch is not a dependency
 * anywhere and should not become one to serve a documentation page, so its claims
 * are cited from published source and cannot be machine-checked.
 *
 * This matters in practice: sklearn's `penalty='l2'` is deprecated as of 1.8. A page
 * asserting library defaults has a shelf life, and it should say whose word it is on.
 */
export type Provenance =
  /** Pinned in this repo's lockfile. `abstraction.test.ts` checks the version. */
  | { kind: 'locked'; pkg: string; version: string }
  /**
   * Read from published documentation or source. Not checkable here, so it carries
   * the date it was read: a claim about a library this repo does not install is only
   * as good as when somebody last looked.
   */
  | { kind: 'cited'; pkg: string; version: string; url: string; checked: string }
  /** This repo's own code. Has no hidden defaults by definition. */
  | { kind: 'ours' }

/** One level of the ladder. Ordered most abstract first. */
export interface Rung {
  id: string
  label: string
  /** One clause naming what this rung is, shown under the label. */
  blurb: string
  provenance: Provenance
}

export type RungCode =
  /**
   * A snippet written for this page, keyed to a <Snippet id> in the model's .mdx.
   * Python and NumPy are authored, because nothing in this repo implements the model
   * in either. Authored code is labelled as such on screen: a reader must never come
   * away thinking the project contains code it does not.
   */
  | { kind: 'authored'; snippet: string }
  /**
   * The real thing, as anchored slices of the model's own source.
   *
   * An ARRAY, not one blob. This is what makes the page survive a large model: the
   * C++ for "initialisation" is one constructor, not a file. extractAnchor is reused
   * unchanged, brace-depth counting and all.
   */
  | { kind: 'source'; refs: CodeRef[] }

/**
 * One thing a library chose on the reader's behalf.
 *
 * `verdict` has three states rather than two on purpose, and the third is the one
 * that keeps the page honest. torch.optim.SGD defaults to momentum=0 and
 * weight_decay=0, which IS the update rule the reader hand-wrote: that is a match,
 * and saying so is what stops the page reading as an argument against libraries.
 * The defaults are mostly good defaults. The point is that they were made for you.
 */
export interface HiddenDefault {
  /** The parameter, as the library names it. */
  name: string
  /** Its default, written the way it appears in a signature. */
  value: string
  verdict:
    /** Does something the model's own code does not do. */
    | 'differs'
    /** Happens to be exactly what the model's own code does. */
    | 'matches'
    /** A knob the model's own code has no concept of. */
    | 'no-equivalent'
  /** One sentence: what it does, and why it matters here. Voice rules apply. */
  note: string
}

/** How one rung expresses one concept. */
export interface Cell {
  rung: string
  code: RungCode
  defaults: HiddenDefault[]
}

/** One idea, across every rung. */
export interface Concept {
  slug: string
  title: string
  /** The question this concept answers, shown as the section heading. */
  question: string
  cells: Cell[]
}

export interface Abstraction {
  /** Ordered, most abstract first. The order IS the ladder, top to bottom. */
  rungs: Rung[]
  concepts: Concept[]
}
