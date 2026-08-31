import type { HiddenDefault } from '../../content/abstraction/types'

// What a library filled in without being asked.
//
// A <dl> on the .kv grid, not a table. There is no <table> anywhere in this app and
// no table CSS to go with one, and a page whose whole argument is "these are
// decisions, not data" reads better as a list of named things than as a spreadsheet.
//
// Three verdicts, and the third is the one that keeps the page honest. Marking a
// default as `matches` says the library chose exactly what you chose: SGD's
// momentum=0 IS the update rule from update(). Without that state the page would be
// an argument against libraries, which it is not meant to be. The defaults are
// mostly sensible. The point is only that somebody else picked them.
//
// Colour follows that meaning: --ok where the library agrees with your code, --warn
// where it went its own way, plain grey where the idea has no counterpart in your
// code at all. --err is deliberately unused, since a difference is not a fault.

const VERDICT_LABEL: Record<HiddenDefault['verdict'], string> = {
  matches: 'same as yours',
  differs: 'differs from yours',
  'no-equivalent': 'no counterpart in yours',
}

export default function DefaultsPanel({ defaults }: { defaults: HiddenDefault[] }) {
  // The C++ rung, and any rung that happens to hide nothing for this concept. Said
  // out loud rather than left blank, because an empty panel is the whole thesis and
  // should read as an answer instead of as missing content.
  if (defaults.length === 0) {
    return (
      <div className="defaults defaults--empty">
        <p className="defaults__none">Nothing. You wrote all of it.</p>
      </div>
    )
  }

  return (
    <div className="defaults">
      <p className="defaults__title">What you did not say</p>
      <dl className="kv defaults__list">
        {defaults.map((d) => (
          <div key={d.name} className={`defaults__item defaults__item--${d.verdict}`}>
            <dt className="defaults__name">
              <span className="defaults__key">{d.name}</span>
              <span className="defaults__value">{d.value}</span>
            </dt>
            <dd className="defaults__note">
              <span className="defaults__verdict">{VERDICT_LABEL[d.verdict]}</span>
              {d.note}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
