// The shape of a walkthrough: what the player needs to render one moment.
//
// The split this file encodes is the central design decision of the feature:
//
//   TIMING, STAGE STATE and CODE ANCHORS are data, and live in a TypeScript
//   manifest (step0/walkthrough.ts). They are numbers and identifiers; putting
//   them in prose would make them unreadable and untestable.
//
//   NARRATION is prose, and lives in MDX (step0/narration.mdx) as <Beat> blocks
//   keyed by scene id. That is not a stylistic preference — it is what keeps the
//   existing build-time pipeline working. remark-math -> rehype-katex renders the
//   derivations, and rehype-shiki highlights any fenced code, both at build time,
//   so no maths or highlighting library reaches the browser. Captions written as
//   TypeScript strings would have to re-solve both, and would fall outside the
//   voice rules in content/README.md that govern everything else on the site.
//
// A scene therefore never carries its own text. It carries an `id`, and the <Beat>
// with that id supplies the words. A test asserts the two sets match exactly, so a
// renamed scene fails the suite instead of rendering a blank caption.

/**
 * A model's source files, imported and highlighted at build time.
 *
 * `raw` is the text, for slicing a function out of it by signature (see anchors.ts).
 * `highlighted` is the same files as HTML, one entry per line, index-aligned with
 * `raw.split('\n')`. Both come from the `?highlight` Vite plugin.
 *
 * This is passed around as a value rather than imported directly by the components
 * that render it. An earlier version had CodePanel import step0's source by name,
 * which quietly made every code-rendering component step0-only: step1 could never
 * have had a walkthrough, and nothing model-generic could reuse the panel.
 */
export interface SourceBundle {
  raw: Record<string, string>
  highlighted: Record<string, string[]>
}

/**
 * The one thing every model's stage union has to agree on.
 *
 * A stage describes what the picture shows, and what it can show is entirely
 * model-specific: step0 draws a neuron and a sigmoid, step1 draws matrices and a
 * layer stack. So the player cannot know the variants. It only needs to know two
 * things, and both are encoded here.
 *
 * First, that there IS a `kind` to switch on. Second, and this is the part worth
 * stating out loud, that a stage drawing nothing is spelled `'none'`. The player
 * holds the previous picture across such a scene rather than blanking (see
 * Walkthrough.tsx), and it decides that by comparing this exact string. A model
 * spelling it 'empty' would compile, render a scene with no picture, and shift the
 * whole page mid-sentence. Use `draws` rather than writing the comparison again.
 */
export type StageState = { kind: string }

/** Whether a stage has a picture of its own, or should hold the previous one. */
export const draws = (stage: StageState): boolean => stage.kind !== 'none'

/** A chapter is a rail entry and a seek target. `slug` IS the URL segment. */
export interface Chapter<Slug extends string = string> {
  slug: Slug
  title: string
}

export type CodeRef<File extends string = string> =
  /**
   * A slice of the REAL shipped source, located by signature (see anchors.ts).
   * Never a line number: an edit above would silently move the range.
   */
  | {
      kind: 'source'
      file: File
      /** Prefix of the signature line, e.g. 'double binaryLoss'. */
      anchor: string
      /** Substrings; lines containing one are shown bright, the rest dimmed. */
      emphasise?: string[]
    }
  /**
   * An authored snippet that is deliberately NOT the shipped C++ — a comparison in
   * another language, or an illustrative form. `note` is rendered as a visible
   * label, because a reader must never take one of these for the real file.
   */
  | {
      kind: 'aside'
      lang: 'cpp' | 'python'
      code: string
      note: string
    }

/**
 * One beat of the walkthrough.
 *
 * `seconds` is a DURATION. Start times are derived by summing (see timeline.ts).
 * Storing absolute starts as well would let one edited duration silently desync
 * everything after it, with nothing to catch it.
 */
export interface Scene<Stage, Slug extends string = string, File extends string = string> {
  /** Must match exactly one <Beat id> in the narration. */
  id: string
  chapter: Slug
  seconds: number
  stage: Stage
  code?: CodeRef<File>
}

/**
 * How the narration is being displayed.
 *
 * 'play' renders only the active beat, in time with the animation. 'text' renders
 * every beat at once, in order — the "Read as text" view, and the reduced-motion
 * default. Both read the same <Beat> blocks, which is what makes the static view
 * generated rather than a second copy of the content maintained by hand.
 */
export type NarrationMode = 'play' | 'text'
