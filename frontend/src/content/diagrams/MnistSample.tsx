// Figure 17 — one real MNIST sample, and the two matrix rows it becomes.
//
// The pixels below are the genuine first image of train-images-idx3-ubyte, not a
// drawing of a five. That matters more than it sounds: a hand-drawn digit would
// have clean edges, and the thing worth seeing here is that a real one does not.
// Regenerate with, from backend/services/Step1/data:
//
//   python3 -c "f=open('train-images-idx3-ubyte','rb');f.read(16);print(f.read(784).hex())"
//
// Everything else on the figure is derived from that string: the normalised
// values in the X row are pixel / 255 exactly as load_idx_images does it, and
// the one-hot Y row is built from LABEL rather than typed out.

import { Grid, Note } from './matrix'
import { m } from './matrix-geometry'

const SIDE = 28
const CELL = 5

/** train-images-idx3-ubyte, image 0. Its label in train-labels is 5. */
const HEX =
  '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000' +
  '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000' +
  '00000000000000000000000000000000000000000000000000000000000000000000000000000000031212127e88af1aa6fff77f00000000' +
  '00000000000000001e245e9aaafdfdfdfdfde1acfdf2c340000000000000000000000031eefdfdfdfdfdfdfdfdfb5d525238270000000000' +
  '0000000000000012dbfdfdfdfdfdc6b6f7f1000000000000000000000000000000000000509c6bfdfdcd0b002b9a00000000000000000000' +
  '0000000000000000000e019afd5a000000000000000000000000000000000000000000000000008bfdbe0200000000000000000000000000' +
  '00000000000000000000000bbefd460000000000000000000000000000000000000000000000000023f1e1a06c0100000000000000000000' +
  '0000000000000000000000000051f0fdfd771900000000000000000000000000000000000000000000002dbafdfd961b0000000000000000' +
  '000000000000000000000000000000105dfcfdbb00000000000000000000000000000000000000000000000000f9fdf94000000000000000' +
  '00000000000000000000000000002e82b7fdfdcf02000000000000000000000000000000000000002794e5fdfdfdfab60000000000000000' +
  '000000000000000000001872ddfdfdfdfdc94e00000000000000000000000000000000001742d5fdfdfdfdc6510200000000000000000000' +
  '00000000000012abdbfdfdfdfdc350090000000000000000000000000000000037ace2fdfdfdfdf4850b0000000000000000000000000000' +
  '0000000088fdfdfdd48784100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000' +
  '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'

const LABEL = 5
const CLASSES = 10

function decode(hex: string): number[] {
  const out: number[] = []
  for (let i = 0; i < hex.length; i += 2) out.push(parseInt(hex.slice(i, i + 2), 16))
  return out
}

const PIXELS = decode(HEX)

// Six consecutive pixels from row 5, chosen because they run from almost nothing
// up into the stroke — a window of six zeros would be true and say nothing.
const WINDOW = 152
const X_ROW = m(
  1,
  6,
  PIXELS.slice(WINDOW, WINDOW + 6).map((v) => v / 255),
)

// The one-hot row load_split writes: all zero except the column named by the label.
const Y_ROW = m(
  1,
  CLASSES,
  Array.from({ length: CLASSES }, (_, j) => (j === LABEL ? 1 : 0)),
)

const IMG = { x: 16, y: 30 }
const RIGHT_CX = 322

export default function MnistSample() {
  return (
    <svg
      viewBox="0 0 480 240"
      width="480"
      height="240"
      role="img"
      aria-labelledby="mnist-sample-title"
      fill="none"
      stroke="currentColor"
      strokeOpacity="0.85"
      vectorEffect="non-scaling-stroke"
    >
      <title id="mnist-sample-title">
        The first image of the MNIST training set, a handwritten five, drawn as a 28 by 28 grid of
        grey squares. Beside it, six consecutive pixels of that image shown as a row of a matrix
        with values 0.01, 0.07, 0.07, 0.07, 0.49 and 0.53, which is pixel brightness divided by
        255. Underneath, the matching row of the truth matrix: ten numbers, all zero except a one
        in column five, because the image is labelled five.
      </title>

      <g fontFamily="var(--font-mono)" fontSize="12" strokeWidth="1.25">
        {/* Only the non-zero pixels get a rect. MNIST is mostly background, so
            this is roughly 150 shapes rather than 784, and the empty border of
            the image is exactly as visible either way. */}
        <rect
          x={IMG.x}
          y={IMG.y}
          width={SIDE * CELL}
          height={SIDE * CELL}
          opacity="0.35"
        />
        {/* crispEdges, because the tiles are translucent fills laid edge to edge.
            With antialiasing on, the shared boundary between two tiles lands on a
            fractional device pixel and neither one fully covers it, so the digit
            picks up a grid of pale seams that looks like part of the data. */}
        <g shapeRendering="crispEdges">
          {PIXELS.map((v, i) =>
            v === 0 ? null : (
              <rect
                key={i}
                x={IMG.x + (i % SIDE) * CELL}
                y={IMG.y + Math.floor(i / SIDE) * CELL}
                width={CELL}
                height={CELL}
                fill="currentColor"
                fillOpacity={v / 255}
                stroke="none"
              />
            ),
          )}
        </g>
        <Note x={IMG.x + (SIDE * CELL) / 2} y={188}>
          image 0 of train-images
        </Note>
        <Note x={IMG.x + (SIDE * CELL) / 2} y={202}>
          28 × 28 = 784 pixels
        </Note>

        <Note x={RIGHT_CX} y={26}>
          one row of X (1 × 784)
        </Note>
        <text x={186} y={53} textAnchor="middle" fill="currentColor" stroke="none" opacity="0.6">
          …
        </text>
        <Grid a={X_ROW} x={195} y={36} cellW={40} />
        <text x={458} y={53} textAnchor="middle" fill="currentColor" stroke="none" opacity="0.6">
          …
        </text>
        <Note x={RIGHT_CX} y={82}>
          every pixel divided by 255,
        </Note>
        <Note x={RIGHT_CX} y={96}>
          so every value lands in [0, 1]
        </Note>

        <Note x={RIGHT_CX} y={134}>
          the matching row of Y (1 × 10)
        </Note>
        <Grid a={Y_ROW} x={185} y={144} cellW={26} emphasis={(_, j) => j === LABEL} />
        <Note x={RIGHT_CX} y={190}>
          labelled {LABEL}, so column {LABEL} holds the 1
        </Note>

        <Note x={240} y={226}>
          784 numbers in, 10 numbers out, and the network never learns it was a picture
        </Note>
      </g>
    </svg>
  )
}
