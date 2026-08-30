// anchors.ts — slicing the real Step0 C++ by function signature.
//
// What these tests catch, stated plainly:
//
//   CAN catch — a wrong slice. Several assertions below run against the ACTUAL
//   imported source rather than a fixture, so if someone edits
//   backend/services/Step0/*.hpp in a way that moves or renames a function, these
//   fail. That is deliberate: it is the anti-drift guarantee the whole
//   build-time-import design was chosen for, and it is the only thing standing
//   between "the code panel shows the wrong function" and nobody noticing.
//
//   CANNOT catch — a slice that is correct but uninteresting to show. Whether a
//   scene points at the right function is an authoring question, covered by the
//   scene/beat consistency test, not here.
//
// The load-bearing case is `binaryLoss`. Step0's members live inside `struct Node`,
// so they close on an indented `    }` while the struct closes on `};` at column 0.
// A /^}/ match — which is what `sed` makes look sufficient — swallows the rest of
// the struct and returns a slice roughly four times too long, with no error.

import { describe, expect, it } from 'vitest'

import { emphasisedLines, extractAnchor, linesIn } from './anchors'
import { STEP0_SOURCE } from '../step0/source'

describe('extractAnchor, against the real Step0 source', () => {
  it('slices a top-level function to its column-0 closing brace', () => {
    const src = STEP0_SOURCE['main.cpp']
    const range = extractAnchor(src, 'void train')
    const text = linesIn(src, range).join('\n')

    expect(text.startsWith('void train(Node& node')).toBe(true)
    expect(text.trimEnd().endsWith('}')).toBe(true)
    // The body, not just the signature.
    expect(text).toContain('node.update(g, lr);')
  })

  it('stops at the INDENTED brace of a struct member, not the struct’s own', () => {
    const src = STEP0_SOURCE['logistic_regression.hpp']
    const range = extractAnchor(src, 'double binaryLoss')
    const text = linesIn(src, range).join('\n')

    expect(text).toContain('const double eps = 1e-7;')
    expect(text).toContain('return loss;')

    // The tell: `gradient` is the next member. If the scan ran to the struct's
    // closing `};` this slice would contain it.
    expect(text).not.toContain('Grad gradient')
    expect(text).not.toContain('void update')

    // And it is the member's brace that ends it, not the struct's.
    const last = linesIn(src, range).at(-1)!
    expect(last).toBe('    }')
  })

  it('handles the last member, whose close is followed by the struct’s', () => {
    const src = STEP0_SOURCE['logistic_regression.hpp']
    const text = linesIn(src, extractAnchor(src, 'void update')).join('\n')

    expect(text).toContain('b -= lr * g.b;')
    // `};` closes the struct on the following line and must be left out.
    expect(text.trimEnd().endsWith('};')).toBe(false)
  })

  it('slices the whole struct when the anchor IS the struct', () => {
    const src = STEP0_SOURCE['logistic_regression.hpp']
    const text = linesIn(src, extractAnchor(src, 'struct Node')).join('\n')

    expect(text).toContain('double forward')
    expect(text).toContain('void update')
    expect(text.trimEnd().endsWith('};')).toBe(true)
  })

  it('slices the one-expression members of math.hpp', () => {
    const src = STEP0_SOURCE['math.hpp']

    const sigmoid = linesIn(src, extractAnchor(src, 'inline double sigmoid')).join('\n')
    expect(sigmoid).toContain('1.0/(1.0+std::exp(-x))')
    expect(sigmoid).not.toContain('inline double dot')

    const dot = linesIn(src, extractAnchor(src, 'inline double dot')).join('\n')
    expect(dot).toContain('total += a[i] * b[i];')
  })
})

describe('extractAnchor, failure modes', () => {
  it('throws on an anchor that matches nothing', () => {
    // Silence would render an empty code panel, which reads as a styling bug and
    // survives review. An exception fails the build instead.
    expect(() => extractAnchor(STEP0_SOURCE['math.hpp'], 'inline double softmax')).toThrow(
      /no line starts with/,
    )
  })

  it('throws on an ambiguous anchor rather than picking the first', () => {
    const src = ['void f() {', '}', 'void f() {', '}'].join('\n')
    expect(() => extractAnchor(src, 'void f')).toThrow(/ambiguous/)
  })

  it('walks past a forward declaration to the definition', () => {
    // Step1/main.cpp declares its functions in a block at the top and defines them
    // hundreds of lines below. The declaration is a strict prefix of the definition,
    // so no longer anchor can tell them apart, and without skipping it the anchor is
    // ambiguous and every main.cpp scene fails.
    const src = [
      'Data make_xor();',
      'double accuracy(MLP& m, const Matrix& X);',
      '',
      'Data make_xor() {',
      '    return {};',
      '}',
    ].join('\n')

    const range = extractAnchor(src, 'Data make_xor')
    expect(range.start).toBe(3)
    expect(linesIn(src, range)).toHaveLength(3)
  })

  it('still throws when only a declaration matches', () => {
    // The skip must not turn "you anchored something with no body" into an empty
    // panel. A prototype with no definition is an authoring mistake, not a slice.
    expect(() => extractAnchor('void f(int x);\n', 'void f')).toThrow(/no line starts with/)
  })

  it('throws when the block never closes', () => {
    expect(() => extractAnchor('void f() {\n  int x = 1;\n', 'void f')).toThrow(/never closes/)
  })

  it('ignores braces inside strings and comments', () => {
    // None of Step0 hits this today, but the failure mode is a silently-long slice
    // rather than an error, so it is worth pinning.
    const src = [
      'void f() {',
      '    std::string s = "{{{";  // }}} and a } here',
      '    /* } */',
      "    char c = '}';",
      '}',
      'void after() {}',
    ].join('\n')

    const text = linesIn(src, extractAnchor(src, 'void f')).join('\n')
    expect(text).not.toContain('void after')
    expect(text.split('\n')).toHaveLength(5)
  })
})

describe('emphasisedLines', () => {
  const lines = ['double p = clamp(x);', 'loss += y * log(p);', 'return loss;']

  it('marks every line containing a needle', () => {
    expect(emphasisedLines(lines, ['loss'])).toEqual(new Set([1, 2]))
  })

  it('treats no needles as "emphasise nothing"', () => {
    // The panel reads an empty set as "all lines at normal weight", never as
    // "dim everything", so an absent `emphasise` must not black out the block.
    expect(emphasisedLines(lines, undefined)).toEqual(new Set())
    expect(emphasisedLines(lines, [])).toEqual(new Set())
  })
})
