import { readFile } from 'node:fs/promises'
import path from 'node:path'

import { codeToTokens } from 'shiki'
import type { Plugin } from 'vite'

import { ncDark } from './src/styles/shiki-theme'

// Syntax-highlights a C++ file at BUILD time and hands the result over one line at
// a time.
//
// `import { lines } from '.../math.hpp?highlight'` gives an array of HTML strings,
// one per source line. The walkthrough's code panel slices that array by function
// (see content/walkthrough/anchors.ts) and renders the slice.
//
// Why a plugin rather than highlighting in the browser: vite.config.ts states the
// rule outright, and it is load-bearing rather than a preference. No highlighter and
// no maths library ships to the client, because the privacy policy commits to there
// being no third-party scripts and the CSP only allows 'self'. Shiki is a build
// dependency here in exactly the way it already is for the MDX pages, and
// `grep -r shiki src/` must keep returning nothing.
//
// Per LINE rather than one blob of HTML because the panel needs to dim the lines a
// scene is not talking about, and to slice a function out of a file. Splitting
// Shiki's finished `<pre>` on `<span class="line">` would work until the day it
// changes its markup; asking for tokens and assembling the lines ourselves is the
// same amount of code and does not depend on that.
//
// Modelled on src/content/rehype-todo-cue.ts, the other local plugin in this repo.

const QUERY = '?highlight'

// Shiki's FontStyle bitmask. Imported as literals rather than the enum so this file
// does not depend on which entry point re-exports it.
const ITALIC = 1
const BOLD = 2
const UNDERLINE = 4

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export default function cppHighlight(): Plugin {
  return {
    name: 'nc-cpp-highlight',
    enforce: 'pre',

    async resolveId(source, importer) {
      if (!source.endsWith(QUERY)) return null
      const file = source.slice(0, -QUERY.length)
      if (!/\.(hpp|cpp|h|cc)$/.test(file)) return null

      // The C++ lives outside the Vite root (backend/services/Step0), so resolve it
      // against the importing module rather than leaving it to the default
      // resolver, which is scoped to the project.
      const base = importer ? path.dirname(importer) : process.cwd()
      return path.resolve(base, file) + QUERY
    },

    async load(id) {
      if (!id.endsWith(QUERY)) return null
      const file = id.slice(0, -QUERY.length)
      if (!/\.(hpp|cpp|h|cc)$/.test(file)) return null

      const raw = await readFile(file, 'utf8')

      // Editing the C++ must rebuild the page that shows it. Without this the dev
      // server keeps serving the highlighted copy from before the edit, which looks
      // exactly like the drift this whole design exists to prevent.
      this.addWatchFile(file)

      const { tokens } = await codeToTokens(raw, { lang: 'cpp', theme: ncDark })

      const lines = tokens.map((line) =>
        line
          .map((token) => {
            const style: string[] = []
            if (token.color) style.push(`color:${token.color}`)
            if (token.fontStyle) {
              if (token.fontStyle & ITALIC) style.push('font-style:italic')
              if (token.fontStyle & BOLD) style.push('font-weight:600')
              if (token.fontStyle & UNDERLINE) style.push('text-decoration:underline')
            }
            const content = escapeHtml(token.content)
            return style.length > 0
              ? `<span style="${style.join(';')}">${content}</span>`
              : content
          })
          .join(''),
      )

      // codeToTokens drops a trailing empty line that split('\n') keeps. The panel
      // indexes this array with ranges computed from the raw text, so the two have
      // to agree on how many lines there are.
      const rawLineCount = raw.split('\n').length
      while (lines.length < rawLineCount) lines.push('')

      return [
        `export const raw = ${JSON.stringify(raw)}`,
        `export const lines = ${JSON.stringify(lines)}`,
      ].join('\n')
    },
  }
}
