import type { ThemeRegistrationRaw } from 'shiki'

// The syntax palette, deliberately capped.
//
// Every stock dark theme Shiki ships is far more colourful than this app allows:
// six or seven hues on screen at once turns a code-heavy learn page into the most
// decorated surface in the product. So this theme uses ONE hue (the muted amber
// that also marks a running job) for literals, and carries every other distinction
// on grey level and weight alone.
//
// The values are the same greys as tokens.css. They are duplicated as literals
// because a TextMate theme is consumed by Shiki at build time, where CSS custom
// properties do not exist. If a token changes there, change it here too.
const TEXT = '#e4e6e8' // --text        identifiers, types, the code you're reading
const DIM = '#9aa0a6' // --text-dim    keywords, punctuation: present but recessive
const FAINT = '#6f7478' // --text-faint comments
const LITERAL = '#a3936a' // --warn      strings and numbers, the only hue here

export const ncDark: ThemeRegistrationRaw = {
  name: 'nc-dark',
  type: 'dark',
  // Shiki writes these onto the <pre>; code.css overrides them so the block
  // matches --bg-raised, but they must be present or Shiki emits no colours.
  colors: {
    'editor.background': '#1d2022',
    'editor.foreground': TEXT,
  },
  settings: [
    { settings: { foreground: TEXT } },
    {
      scope: ['comment', 'punctuation.definition.comment'],
      settings: { foreground: FAINT, fontStyle: 'italic' },
    },
    {
      // Keywords recede rather than shout: in a walkthrough the reader is
      // following the identifiers and the shape, not hunting for `return`.
      scope: [
        'keyword',
        'storage',
        'storage.modifier',
        'keyword.control',
        'keyword.operator',
        'keyword.control.directive',
        'meta.preprocessor',
        'punctuation',
        'punctuation.separator',
        'punctuation.terminator',
        'meta.brace',
      ],
      settings: { foreground: DIM },
    },
    {
      scope: [
        'string',
        'string.quoted',
        'constant.numeric',
        'constant.language',
        'constant.character.escape',
      ],
      settings: { foreground: LITERAL },
    },
    {
      scope: ['entity.name.function', 'support.function', 'meta.function-call'],
      settings: { foreground: TEXT, fontStyle: 'bold' },
    },
    {
      scope: [
        'storage.type',
        'entity.name.type',
        'entity.name.class',
        'support.type',
        'support.class',
        'variable',
        'variable.parameter',
        'variable.other',
        'entity.name.namespace',
      ],
      settings: { foreground: TEXT },
    },
  ],
}
