// Locating a function inside a C++ source string, by signature rather than by line
// number.
//
// The walkthrough's code panel shows slices of the real Step0 source (see
// step0/source.ts). Addressing those slices by line number would defeat the point:
// adding a comment near the top of a file would silently shift every range below it
// and the panel would start showing the wrong code with no error. An anchor is a
// prefix of the signature line, so an edit elsewhere in the file cannot move it.
//
// Finding the END of a function is the part that has to be done properly. Step0's
// functions are NOT all top-level: `forward`, `binaryLoss`, `gradient` and `update`
// are members of `struct Node`, so they are indented and close on `    }`, while the
// struct itself closes on `};` at column 0. Matching /^}/ — the obvious shortcut,
// and the one `sed` makes look sufficient — finds the struct's closing brace for
// every one of them and returns a slice four times too long. So: count depth.
//
// Depth counting in turn has to ignore braces that are not code. A brace inside a
// string literal or a comment would unbalance the count and run the slice to the end
// of the file. Step0 happens to contain none today, but the failure mode is a silent
// wrong answer rather than an error, which is exactly the kind of thing that is
// cheap to prevent now and miserable to diagnose later.

export interface LineRange {
  /** 0-indexed, inclusive. */
  start: number
  /** 0-indexed, inclusive. */
  end: number
}

type ScanState = {
  depth: number
  inBlockComment: boolean
}

/**
 * Advance the brace depth across one line, ignoring braces inside line comments,
 * block comments, string literals and character literals.
 *
 * Returns the new state. `depth` may legitimately go negative if called on a line
 * below the region of interest; callers stop before that matters.
 */
function scanLine(line: string, state: ScanState): ScanState {
  let { depth, inBlockComment } = state

  for (let i = 0; i < line.length; i++) {
    const c = line[i]
    const next = line[i + 1]

    if (inBlockComment) {
      if (c === '*' && next === '/') {
        inBlockComment = false
        i++
      }
      continue
    }

    // A line comment ends the line for our purposes.
    if (c === '/' && next === '/') break

    if (c === '/' && next === '*') {
      inBlockComment = true
      i++
      continue
    }

    // Skip over a string or character literal wholesale. Escapes matter: "\"" is
    // one character, not the start of a new literal.
    if (c === '"' || c === "'") {
      const quote = c
      i++
      while (i < line.length) {
        if (line[i] === '\\') {
          i++ // skip the escaped character
        } else if (line[i] === quote) {
          break
        }
        i++
      }
      continue
    }

    if (c === '{') depth++
    else if (c === '}') depth--
  }

  return { depth, inBlockComment }
}

/**
 * The line range of the declaration whose signature line starts with `anchor`.
 *
 * `anchor` is matched against the trimmed start of each line, so
 * `extractAnchor(src, 'double binaryLoss')` finds the member without caring how far
 * it is indented.
 *
 * Throws rather than returning an empty range when the anchor is missing or
 * ambiguous. An empty range renders an empty code panel, which reads as a styling
 * bug and would survive review; an exception fails the test that pins it.
 */
export function extractAnchor(source: string, anchor: string): LineRange {
  const lines = source.split('\n')

  // A forward declaration is skipped, and it has to be, because no longer anchor can
  // separate it from its definition: Step1/main.cpp declares `Data make_xor();` at
  // the top and defines `Data make_xor() {` four hundred lines below, and the whole
  // of the first is a prefix of the second. Without this the anchor is ambiguous and
  // throws, which is at least loud, but there is no anchor string that fixes it.
  //
  // Ending in `;` is the test because this function returns the range of a BLOCK. A
  // declaration has no body to slice, so a line that ends the statement outright can
  // never be the answer, whether it collides with a definition or not.
  const matches: number[] = []
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (line.startsWith(anchor) && !line.endsWith(';')) matches.push(i)
  }

  if (matches.length === 0) {
    throw new Error(`extractAnchor: no line starts with ${JSON.stringify(anchor)}`)
  }
  if (matches.length > 1) {
    throw new Error(
      `extractAnchor: ${JSON.stringify(anchor)} is ambiguous, matching lines ` +
        `${matches.map((n) => n + 1).join(', ')}. Lengthen the anchor.`,
    )
  }

  const start = matches[0]
  let state: ScanState = { depth: 0, inBlockComment: false }
  let opened = false

  for (let i = start; i < lines.length; i++) {
    state = scanLine(lines[i], state)
    if (state.depth > 0) opened = true
    // Closed again after having opened: this line carries the matching brace.
    if (opened && state.depth <= 0) return { start, end: i }
  }

  throw new Error(
    `extractAnchor: ${JSON.stringify(anchor)} at line ${start + 1} never closes. ` +
      `Unbalanced braces, or the anchor matched something that is not a block.`,
  )
}

/** The lines of `source` in `range`, as an array. */
export function linesIn(source: string, range: LineRange): string[] {
  return source.split('\n').slice(range.start, range.end + 1)
}

/**
 * Which lines of a slice to render bright, the rest dimmed.
 *
 * Needles are substrings rather than line numbers, for the same reason anchors are:
 * a line number would silently point at the wrong line after any edit above it. An
 * empty or absent needle list means "emphasise nothing", which the panel renders as
 * "everything at normal weight" rather than "everything dimmed".
 */
export function emphasisedLines(lines: string[], needles: string[] | undefined): Set<number> {
  const hit = new Set<number>()
  if (!needles || needles.length === 0) return hit
  lines.forEach((line, i) => {
    if (needles.some((n) => line.includes(n))) hit.add(i)
  })
  return hit
}
