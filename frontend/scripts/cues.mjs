// Lists every unfilled ```todo cue in the authored content.
//
// The rendered cue (see src/content/rehype-todo-cue.ts) is the guard that stops a
// placeholder being mistaken for prose *while reading a page*. This is the other
// half: answering "is anything unfinished anywhere?" without opening every page.
//
// Exits 0 either way. This reports; it does not gate the build — an unfinished
// page is a normal state to be in while authoring, and a script that failed
// `npm run build` would just get worked around.

import { readdir, readFile } from 'node:fs/promises'
import { join, relative } from 'node:path'

const CONTENT = new URL('../src/content/', import.meta.url).pathname
// Match what CommonMark accepts, not just the flush-left three-backtick case: a
// fence may be indented up to 3 spaces and may use more than 3 backticks. The
// plugin sees remark's parsed output and so honours all of those; if this script
// were stricter it would report "no unfilled cues" for a page that renders one —
// a false clean from the tool whose whole job is to find them.
const FENCE_OPEN = /^\s{0,3}`{3,}todo\s*$/
const FENCE_CLOSE = /^\s{0,3}`{3,}\s*$/

async function mdxFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true })
  const found = await Promise.all(
    entries.map((entry) => {
      const path = join(dir, entry.name)
      if (entry.isDirectory()) return mdxFiles(path)
      return entry.name.endsWith('.mdx') ? [path] : []
    }),
  )
  return found.flat()
}

/** Every ```todo fence in one file, as { line, body }. */
function cuesIn(source) {
  const lines = source.split('\n')
  const cues = []
  for (let i = 0; i < lines.length; i++) {
    if (!FENCE_OPEN.test(lines[i])) continue
    const body = []
    // Scan to the closing fence. An unterminated fence runs to end-of-file,
    // which is still worth reporting rather than silently skipping.
    let j = i + 1
    while (j < lines.length && !FENCE_CLOSE.test(lines[j])) body.push(lines[j++])
    cues.push({ line: i + 1, body: body.join('\n').trim() })
    i = j
  }
  return cues
}

const files = (await mdxFiles(CONTENT)).sort()
let total = 0

for (const file of files) {
  const cues = cuesIn(await readFile(file, 'utf8'))
  for (const cue of cues) {
    // file:line, so the terminal can open it directly.
    console.log(`${relative(process.cwd(), file)}:${cue.line}`)
    for (const line of (cue.body || '(empty)').split('\n')) console.log(`    ${line}`)
    console.log()
    total++
  }
}

console.log(
  total === 0
    ? `No unfilled cues in ${files.length} pages.`
    : `${total} unfilled ${total === 1 ? 'cue' : 'cues'} in ${files.length} pages.`,
)
