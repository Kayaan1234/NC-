import type { Root, RootContent, Element } from 'hast'

// Turns a ```todo fence in an .mdx page into a loud, obviously-unfinished block.
//
// This exists because of a specific failure that reached the live site: a page
// carried the lines `#latex sigmoid` and `#diagram of sigmoid` as placeholders,
// and because they had no space after the `#` CommonMark treated them as ordinary
// paragraphs. They rendered as body text, looked like prose, and nobody noticed.
//
// So the requirement for a cue is not "a convention we agree on" — it is that an
// unfilled one CANNOT be mistaken for finished content. Hence a block that
// announces itself, plus `npm run cues` to find them from the terminal.
//
// Runs before rehypeShiki in the plugin chain so the highlighter never sees the
// fence: `todo` is not a language, and this keeps it from being syntax-coloured
// as if it were code the reader should read.

const CUE_LANGUAGE = 'language-todo'

// Root and its content share no single base type in hast, and Doctype has no
// `children` at all, so the walk below works over the union.
type Node = Root | RootContent

// Any node carrying children. The walk tests for this structurally rather than
// checking `type === 'element'`, because MDX components (`<Figure>` …) arrive as
// `mdxJsxFlowElement` nodes, which are not hast elements and are not in the union
// above. An element-only walk never looked inside them, so a ```todo fence
// written between JSX tags was left for rehypeShiki to syntax-colour into an
// ordinary, finished-looking code block — the precise failure this file exists to
// prevent, reappearing one level down. Caught by building a probe fence inside a
// <Figure> and reading the bundle, not by reasoning about the tree.
type Parent = { children: Node[] }

function isParent(node: unknown): node is Parent {
  return typeof node === 'object' && node !== null && Array.isArray((node as Parent).children)
}

function classNames(node: Element): string[] {
  const value: unknown = node.properties?.className
  if (Array.isArray(value)) return value.map(String)
  if (typeof value === 'string') return value.split(/\s+/)
  return []
}

function textOf(node: Node): string {
  if (node.type === 'text') return node.value
  if ('children' in node) return (node.children as Node[]).map(textOf).join('')
  return ''
}

/** The <pre> wrapping a ```todo fence, or null for anything else. */
function cueBody(node: Node): string | null {
  if (node.type !== 'element' || node.tagName !== 'pre') return null
  const code = node.children.find(
    (child): child is Element => child.type === 'element' && child.tagName === 'code',
  )
  if (!code || !classNames(code).includes(CUE_LANGUAGE)) return null
  return textOf(code).trim()
}

function cueElement(body: string): Element {
  return {
    type: 'element',
    tagName: 'div',
    properties: { className: ['cue'], role: 'note' },
    children: [
      {
        type: 'element',
        tagName: 'p',
        properties: { className: ['cue__label'] },
        children: [{ type: 'text', value: 'To do: not yet filled in' }],
      },
      {
        type: 'element',
        tagName: 'p',
        properties: { className: ['cue__body'] },
        children: [{ type: 'text', value: body }],
      },
    ],
  }
}

export default function rehypeTodoCue() {
  return (tree: Root) => {
    const walk = (node: Parent) => {
      node.children = node.children.map((child) => {
        const body = cueBody(child)
        if (body !== null) return cueElement(body)
        if (isParent(child)) walk(child)
        return child
      })
    }
    walk(tree)
  }
}
