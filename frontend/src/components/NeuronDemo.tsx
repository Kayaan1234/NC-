import { useEffect, useMemo, useRef, useState } from 'react'
import { run, type DatasetName, type LogLine } from '../demo'

// The landing page's running terminal: a real Rung 0 neuron training in the
// browser, printing what Step0/main.cpp prints. See demo.ts for the arithmetic.
//
// The pacing is a setInterval advancing a line count, NOT a CSS animation. This
// codebase contains no @keyframes anywhere and the token file caps the animation
// budget at colour transitions (--t), so a log that types itself has to earn its
// motion from state rather than from a stylesheet. Reduced motion skips the timer
// entirely and renders the finished log.

const LINE_MS = 90

// A log line splits into runs of digits and everything else, so numbers can take
// the --warn treatment. That is not a new accent: shiki-theme.ts already colours
// numeric literals --warn as "the only hue here", and it is what makes the loss
// column readable as a falling quantity rather than as text.
const NUMERIC = /(\d+\.?\d*)/g

function Line({ line }: { line: LogLine }) {
  // The header and RESULT lines are chrome around the run, not the run: keeping
  // them dim stops the eye landing on a JSON blob instead of on the loss column.
  const dim = line.kind === 'header' || line.kind === 'result'
  return (
    <div className={dim ? 'demo__line demo__line--dim' : 'demo__line'}>
      {line.text.split(NUMERIC).map((part, i) =>
        // split() with one capture group puts the captures at the odd indices.
        i % 2 === 1 ? (
          <span key={i} className="demo__num">
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </div>
  )
}

export default function NeuronDemo() {
  const [dataset, setDataset] = useState<DatasetName>('tiny')
  // Bumped by "Run again" to restart the reveal without recomputing the run.
  const [attempt, setAttempt] = useState(0)
  const [shown, setShown] = useState(0)
  const logRef = useRef<HTMLDivElement>(null)

  const result = useMemo(() => run(dataset), [dataset])
  const total = result.lines.length
  const done = shown >= total

  useEffect(() => {
    // Read the preference at run time rather than through a media query in CSS:
    // the thing being suppressed is a JS timer, not a declaration.
    const still =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (still) {
      setShown(total)
      return
    }

    // The line counter lives here rather than being read back out of state. An
    // earlier version decided when to stop inside the setShown updater, which put
    // a clearInterval side effect in a function React is free to call twice (it
    // does, under StrictMode) — switching datasets fast enough could then kill the
    // new run's interval and leave the log frozen mid-epoch, still saying
    // "running". Keeping the count local makes the updater pure and the stop
    // condition exact.
    setShown(0)
    let n = 0
    const id = setInterval(() => {
      n += 1
      setShown(n)
      if (n >= total) clearInterval(id)
    }, LINE_MS)
    // Covers unmount, a dataset switch mid-run, and "Run again" — without this a
    // fast switch leaves the previous run's interval writing into the new one.
    return () => clearInterval(id)
  }, [dataset, attempt, total])

  // Follow the output down as it arrives, the way a terminal does. Skipped once
  // the run finishes so the block doesn't fight a user who scrolls back up.
  useEffect(() => {
    if (logRef.current && !done) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [shown, done])

  const visible = result.lines.slice(0, shown)
  // Before the first line lands there is no state to read, so hold at the
  // starting weights rather than rendering an empty row that then pops in.
  const state = visible[visible.length - 1] ?? result.lines[0]

  // Only the dataset changes here. Resetting `shown` is the effect's job — doing
  // it in both places is how the two got out of step in the first place.
  function pick(next: DatasetName) {
    setDataset(next)
  }

  return (
    <div className="demo">
      <div className="demo__bar">
        <div className="demo__tabs" role="group" aria-label="Dataset">
          {(['tiny', 'xor'] as const).map((name) => (
            <button
              key={name}
              type="button"
              className={name === dataset ? 'demo__tab demo__tab--on' : 'demo__tab'}
              aria-pressed={name === dataset}
              onClick={() => pick(name)}
            >
              {name}
            </button>
          ))}
        </div>
        <span className={done ? 'status status--succeeded' : 'status status--running'}>
          {done ? 'finished' : 'running'}
        </span>
      </div>

      {/* What training actually changes. A column of loss values shows that
          something is happening; this shows what. On xor it collapses to zeros,
          which is the failure made visible rather than described. */}
      <div className="demo__weights">
        w = [{' '}
        {state.w.map((v, i) => (
          <span key={i}>
            <span className="demo__num">{v.toFixed(4)}</span>
            {i < state.w.length - 1 ? ', ' : ''}
          </span>
        ))}{' '}
        ] b = <span className="demo__num">{state.b.toFixed(4)}</span>
      </div>

      {/* Deliberately not a live region. A screen reader would read every epoch
          line as it arrived, which is 13 interruptions to say one thing; the
          role="status" summary below announces the outcome once instead.

          tabIndex is what makes it reachable: the RESULT line is wider than the
          box, and a scroll container that no key can reach puts that content out
          of a keyboard user's hands entirely. */}
      <div
        className="demo__log"
        ref={logRef}
        tabIndex={0}
        role="group"
        aria-label={`Training log, dataset ${dataset}`}
      >
        {visible.map((line, i) => (
          <Line key={i} line={line} />
        ))}
      </div>

      <div className="demo__foot">
        <p className="demo__summary" role="status">
          {!done
            ? ''
            : result.solved
              ? `The neuron separated ${dataset}: 100% accuracy, loss near zero.`
              : 'The loss stopped at 0.6931 which is about ln 2, the loss of a coin flip. ' +
                'A single neuron is a straight-line cut, and no straight line separates XOR. ' +
                'That is the reason Rung 1 adds a hidden layer.'}
        </p>
        <button
          type="button"
          className="btn-quiet demo__again"
          onClick={() => setAttempt((n) => n + 1)}
        >
          Run again
        </button>
      </div>
    </div>
  )
}
