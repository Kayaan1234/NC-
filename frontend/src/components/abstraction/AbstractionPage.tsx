import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import DefaultsPanel from './DefaultsPanel'
import { SnippetProvider } from './Snippet'
import { SourceBlock } from '../walkthrough/CodePanel'
import type { Cell, Provenance, Rung } from '../../content/abstraction/types'
import type { ModelContent } from '../../content/types'

// The closing page of a model's learn flow: the same model at four levels of
// abstraction, and what each level decided for you.
//
// Concept-major, and that is the decision the whole layout turns on. Rung-major
// (pick a library, see its whole implementation) reads well for one neuron and falls
// apart at Rung 1, where the C++ column would be matrix.hpp plus layer.hpp plus
// MLP.hpp on one screen. Asking "how does each rung initialise weights" keeps every
// cell to a few lines however large the model gets, and it puts the four answers
// next to each other, which is the only place the comparison actually lands.
//
// The ladder is the vertical axis of the page rather than a control. Most abstract
// at the top, your own code at the bottom, and the defaults column thinning out as
// you go down until it is empty. Nothing here moves, so there is no clock and no
// motion to suppress under prefers-reduced-motion.

function ProvenanceNote({ provenance }: { provenance: Provenance }) {
  if (provenance.kind === 'ours') return null

  if (provenance.kind === 'locked') {
    return (
      <span className="ladder__provenance">
        {provenance.pkg} {provenance.version}, pinned in this repo
      </span>
    )
  }

  return (
    <span className="ladder__provenance">
      {provenance.pkg} {provenance.version}, read from{' '}
      <a href={provenance.url} target="_blank" rel="noreferrer noopener">
        the source
      </a>{' '}
      on {provenance.checked}
    </span>
  )
}

export default function AbstractionPage({
  modelId,
  content,
}: {
  modelId: string
  // The caller has already checked this model has an epilogue.
  content: ModelContent & { epilogue: NonNullable<ModelContent['epilogue']> }
}) {
  const { epilogue, sources } = content
  const { abstraction, Snippets } = epilogue
  const [conceptSlug, setConceptSlug] = useState(abstraction.concepts[0].slug)

  const concept =
    abstraction.concepts.find((c) => c.slug === conceptSlug) ?? abstraction.concepts[0]

  // What each rung decided for you, across the whole page. Counted from the
  // manifest rather than written down, so it cannot fall out of step with the
  // panels above it.
  //
  // Split by verdict, and the split is the point. Counting decisions alone says
  // scikit-learn and PyTorch hide the same amount, which is true and uninteresting.
  // Counting how many of them DIFFER from the code you wrote says something better:
  // the two libraries hide a similar number of choices and disagree with you about
  // completely different amounts of them.
  const tally = useMemo(
    () =>
      abstraction.rungs.map((r) => {
        const defaults = abstraction.concepts.flatMap(
          (c) => c.cells.find((cell) => cell.rung === r.id)?.defaults ?? [],
        )
        return {
          rung: r,
          total: defaults.length,
          differs: defaults.filter((d) => d.verdict === 'differs').length,
        }
      }),
    [abstraction],
  )

  // Rail entries are whatever the main flow calls its parts, so this works for a
  // walkthrough's chapters and a paged model's sections without branching further.
  const priorEntries =
    content.kind === 'walkthrough'
      ? content.chapters.map((c) => ({ slug: c.slug, title: c.title }))
      : content.sections.map((s) => ({ slug: s.slug, title: s.title }))

  function renderCode(cell: Cell, rung: Rung) {
    if (cell.code.kind === 'authored') {
      return (
        <div className="codepanel">
          {/* Labelled, always. Nothing in this repo implements the model in Python,
              and a reader must never leave thinking otherwise. Same rule the
              walkthrough's aside blocks follow. */}
          <div className="codepanel__name codepanel__name--aside">
            {rung.label}, written for this page
          </div>
          <div className="codepanel__code codepanel__code--snippet">
            <SnippetProvider value={cell.code.snippet}>
              <Snippets />
            </SnippetProvider>
          </div>
        </div>
      )
    }

    if (!sources) return null
    return (
      <div className="codepanel">
        {cell.code.refs.map((ref) =>
          ref.kind === 'source' ? (
            <SourceBlock
              key={`${ref.file}:${ref.anchor}`}
              sources={sources}
              file={ref.file}
              anchor={ref.anchor}
              emphasise={ref.emphasise}
            />
          ) : null,
        )}
      </div>
    )
  }

  return (
    <div className="learn-grid">
      <nav className="learn-rail" aria-label="Sections">
        <Link to="/training" className="learn-rail__back">
          &larr; All models
        </Link>
        <div className="learn-rail__model">{content.name}</div>
        <div className="learn-rail__count">Python</div>

        <div className="learn-rail__list">
          {priorEntries.map((e) => (
            <Link
              key={e.slug}
              to={`/training/${modelId}/learn/${e.slug}`}
              className="learn-rail__item"
            >
              {e.title}
            </Link>
          ))}
          <span className="learn-rail__item learn-rail__item--current" aria-current="page">
            {epilogue.title}
          </span>
        </div>

        <div className="learn-rail__foot">
          <Link to={`/training/${modelId}/bridge`}>Find a dataset &rarr;</Link>
          <Link to={`/training/${modelId}`}>Start training &rarr;</Link>
        </div>
      </nav>

      <div className="learn-body">
        <div className="prose">
          <h1>{epilogue.title}</h1>
          <p>
            You have built this model once already, from the maths down. Here it is
            four more times, starting from the call you would actually reach for in
            Python. Each rung does the same job. None of them does it the same way,
            and the column on the right is why.
          </p>
        </div>

        <div className="ladder__concepts" role="group" aria-label="Concept">
          {abstraction.concepts.map((c) => (
            <button
              key={c.slug}
              type="button"
              className={
                c.slug === concept.slug ? 'ladder__concept ladder__concept--on' : 'ladder__concept'
              }
              aria-pressed={c.slug === concept.slug}
              onClick={() => setConceptSlug(c.slug)}
            >
              {c.title}
            </button>
          ))}
        </div>

        <h2 className="ladder__question">{concept.question}</h2>

        <ol className="ladder">
          {abstraction.rungs.map((rung) => {
            const cell = concept.cells.find((c) => c.rung === rung.id)
            if (!cell) return null
            return (
              <li key={rung.id} className="ladder__rung">
                <div className="ladder__head">
                  <span className="ladder__label">{rung.label}</span>
                  <span className="ladder__blurb">{rung.blurb}</span>
                  <ProvenanceNote provenance={rung.provenance} />
                </div>
                <div className="ladder__body">
                  <div className="ladder__code">{renderCode(cell, rung)}</div>
                  <DefaultsPanel defaults={cell.defaults} />
                </div>
              </li>
            )
          })}
        </ol>

        <div className="tally">
          <p className="tally__title">Decisions made for you, across this whole page</p>
          <ul className="tally__list">
            <li className="tally__row tally__row--head">
              <span />
              <span>differ from yours</span>
              <span>total</span>
            </li>
            {tally.map(({ rung, total, differs }) => (
              <li key={rung.id} className="tally__row">
                <span className="tally__rung">{rung.label}</span>
                <span className="tally__count">{differs}</span>
                <span className="tally__count tally__count--quiet">{total}</span>
              </li>
            ))}
          </ul>
          <p className="tally__note">
            Look at the first two rows. scikit-learn and PyTorch make you about the
            same number of decisions, and they are decisions of completely different
            kinds. Most of what PyTorch picks is what you picked, and the couple of
            places it goes its own way are places it will tell you about. scikit-learn
            quietly swapped your optimiser for a quasi-Newton method and added a
            penalty term to your loss, and the call still reads as one line.
          </p>
          <p className="tally__note">
            None of that is a mistake, and none of it is an argument for writing your
            own. Most of these defaults are what you would have chosen anyway. The
            reason to know them is that a library you cannot see inside is a library
            you cannot debug, and having written the thing yourself once is what lets
            you see inside it.
          </p>
        </div>

        <nav className="learn-nav" aria-label="Section pagination">
          <span>
            <Link to={`/training/${modelId}/learn`}>&larr; Back to the walkthrough</Link>
          </span>
          <span>
            <Link to={`/training/${modelId}`}>Start training &rarr;</Link>
          </span>
        </nav>
      </div>
    </div>
  )
}
