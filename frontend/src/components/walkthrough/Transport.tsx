import type { Chapter } from '../../content/walkthrough/types'
import { chapterTicks, formatTime } from '../../content/walkthrough/timeline'
import type { TimedScene } from '../../content/walkthrough/timeline'

// Play, pause, scrub, speed.
//
// The scrub bar is a real <input type="range">. A div with a drag handler would look
// the same and would have to reimplement keyboard control, focus, touch dragging and
// screen reader semantics, all of which the input already has and gets right. The
// chapter ticks are drawn behind it as absolutely positioned marks, so the input
// itself stays a plain, unstyled-in-behaviour control.
//
// Rate is a small set of buttons rather than a <select>, because a select on this
// row would be the only dropdown on the page and reads as a form control in the
// middle of a player.

const RATES = [0.75, 1, 1.5, 2]

export default function Transport({
  t,
  total,
  playing,
  rate,
  scenes,
  chapters,
  onToggle,
  onSeek,
  onRate,
}: {
  t: number
  total: number
  playing: boolean
  rate: number
  scenes: readonly TimedScene[]
  chapters: readonly Chapter[]
  onToggle: () => void
  onSeek: (seconds: number) => void
  onRate: (rate: number) => void
}) {
  const ticks = chapterTicks(scenes, chapters)

  return (
    <div className="transport">
      <button
        type="button"
        className="transport__play"
        onClick={onToggle}
        aria-label={playing ? 'Pause' : 'Play'}
      >
        {/* Glyphs rather than icons: the rest of the app draws its chrome in text
            and a lone icon set here would be the only one in the product. */}
        <span aria-hidden="true">{playing ? '❙❙' : '▶'}</span>
      </button>

      <div className="transport__track">
        <div className="transport__ticks" aria-hidden="true">
          {ticks.map((tick) => (
            <span key={tick.slug} className="transport__tick" style={{ left: `${tick.at * 100}%` }} />
          ))}
        </div>
        <input
          type="range"
          className="transport__range"
          min={0}
          max={total}
          step={0.1}
          value={t}
          onChange={(e) => onSeek(Number(e.target.value))}
          aria-label="Seek"
          // The raw number of seconds is unreadable aloud; this is what a screen
          // reader announces as the handle moves.
          aria-valuetext={`${formatTime(t)} of ${formatTime(total)}`}
        />
      </div>

      <div className="transport__time">
        <span className="transport__elapsed">{formatTime(t)}</span>
        <span className="transport__sep"> / </span>
        <span>{formatTime(total)}</span>
      </div>

      <div className="transport__rates" role="group" aria-label="Playback speed">
        {RATES.map((r) => (
          <button
            key={r}
            type="button"
            className={r === rate ? 'transport__rate transport__rate--on' : 'transport__rate'}
            aria-pressed={r === rate}
            onClick={() => onRate(r)}
          >
            {r}&times;
          </button>
        ))}
      </div>
    </div>
  )
}
