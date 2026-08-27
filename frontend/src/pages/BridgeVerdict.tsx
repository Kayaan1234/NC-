import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import Message from '../components/Message'
import VerifyNotice from '../components/VerifyNotice'
import { message } from '../train'
import { VERDICT_PRESENTATION, bridgePath, formatRows, type BridgeVerdictRecord } from '../bridge'

// One dataset, for one model. The page a student lands on when they have picked
// a topic and want to get going.
//
// What it shows, and nothing else: whether this works, what the data is, why it
// suits (or does not suit) this model, and how they will know they are done.
// Every measurement behind those answers still travels with the artefact, but
// it lives in the closed disclosure at the bottom, because a page that opens
// with accuracy tables and rejection counts teaches a student about the search
// rather than about their project.

export default function BridgeVerdict() {
  const { user } = useAuth()
  const { modelId = '', topicSlug = '' } = useParams()
  const [record, setRecord] = useState<BridgeVerdictRecord | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user?.verified) {
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const fetched = await api<BridgeVerdictRecord>(
          `/bridge/verdicts/${topicSlug}/${modelId}`,
          { method: 'GET', auth: true },
        )
        if (!cancelled) setRecord(fetched)
      } catch (err) {
        if (!cancelled) setError(message(err, 'Could not load this dataset'))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [user, topicSlug, modelId])

  if (!user) return null
  if (!user.verified) return <VerifyNotice />

  const artefact = record?.verdict
  const presentation = artefact ? VERDICT_PRESENTATION[artefact.verdict] : undefined
  const dataset = artefact?.dataset
  const rows = dataset?.scale?.num_rows as number | undefined
  const columns = dataset?.scale?.num_columns as number | undefined

  return (
    <div className="container-app">
      <p className="backlink">
        <Link to={bridgePath(modelId)}>&larr; Find a dataset</Link>
      </p>

      {loading && <p className="page-status">Loading...</p>}
      {error && <Message kind="error">{error}</Message>}

      {artefact && record && (
        <>
          <div className="page-header">
            <h1>{record.topic_display}</h1>
            <p>For the {(record.step_name ?? artefact.display_name).toLowerCase()} you are building.</p>
          </div>

          <div className={`verdict-banner verdict-banner--${presentation?.tone ?? 'warn'}`}>
            <strong>{presentation?.label ?? artefact.verdict}</strong>
            <p>{artefact.summary}</p>
          </div>

          {dataset && (
            <div className="section">
              <h2 className="section__title">The data</h2>
              <div className="card">
                <div className="dataset__name">{dataset.title || dataset.dataset_id}</div>
                <div className="dataset__facts">
                  {[
                    formatRows(rows),
                    typeof columns === 'number' ? `${columns} columns` : '',
                    record.plain_difficulty ?? '',
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </div>
                <div className="dataset__licence">{record.plain_license}</div>
                <a
                  className="cta"
                  href={dataset.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Get the data &rarr;
                </a>
              </div>
            </div>
          )}

          {record.plain_fit && (
            <div className="section">
              {/* The heading has to follow the answer. "Why it suits this model"
                  above a sentence explaining that it does not is the kind of
                  small contradiction that makes a reader distrust the page. */}
              <h2 className="section__title">
                {artefact.fit.outcome === 'pass'
                  ? 'Why it suits this model'
                  : artefact.fit.outcome === 'fail'
                    ? 'Why it does not suit this model'
                    : 'How it fits this model'}
              </h2>
              <p className="lede">{record.plain_fit}</p>
            </div>
          )}

          {artefact.api_path && artefact.api_path.length > 0 && (
            <div className="section">
              <h2 className="section__title">Where to get it</h2>
              <div className="card">
                <div className="dataset__name">{artefact.api_path[0].name}</div>
                <div className="dataset__facts">
                  About {artefact.api_path[0].estimated_collection_days}{' '}
                  {artefact.api_path[0].estimated_collection_days === 1 ? 'day' : 'days'} of
                  collecting to get enough
                  {artefact.api_path[0].auth !== 'none' && ', and you will need a free key'}
                </div>
                <a className="cta" href={artefact.api_path[0].docs_url} target="_blank" rel="noreferrer">
                  Read the docs &rarr;
                </a>
              </div>
            </div>
          )}

          {artefact.nearest_domain && artefact.nearest_domain.length > 0 && (
            <div className="section">
              <h2 className="section__title">Closest things that do have data</h2>
              <ul className="model-list">
                {artefact.nearest_domain.map((near) => (
                  <li key={near.dataset_id}>
                    <a className="model" href={near.url ?? '#'} target="_blank" rel="noreferrer">
                      <div className="model__name">{near.title ?? near.dataset_id}</div>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="section">
            <h2 className="section__title">You will know it worked when</h2>
            <p className="lede">{record.plain_done ?? artefact.definition_of_done}</p>
          </div>

          <details className="details">
            <summary>How I checked this</summary>
            <div className="details__body">
              <p>
                I ran {artefact.evidence.queries.length} searches and looked at{' '}
                {artefact.evidence.candidates_considered} datasets
                {artefact.evidence.replan_rounds > 0 &&
                  `, changing tack ${artefact.evidence.replan_rounds} time${artefact.evidence.replan_rounds === 1 ? '' : 's'} when nothing fit`}
                .
              </p>
              {Object.entries(artefact.evidence.rejections).some(([, e]) => e.count > 0) && (
                <ul>
                  {Object.entries(artefact.evidence.rejections)
                    .filter(([, entry]) => entry.count > 0)
                    .map(([gate, entry]) => (
                      <li key={gate}>
                        {entry.count} ruled out on {gate}
                        {entry.examples[0] && `, for example ${entry.examples[0].reason}`}
                      </li>
                    ))}
                </ul>
              )}
              {artefact.fit.probed && artefact.fit.means && (
                <p>
                  Fit test on {artefact.fit.rows_used?.toLocaleString()} rows, best of each
                  approach:{' '}
                  {Object.entries(artefact.fit.means)
                    .map(([variant, value]) => `${variant} ${(value * 100).toFixed(1)}%`)
                    .join(', ')}
                  . Anything under {((artefact.fit.noise_band ?? 0) * 100).toFixed(1)}% apart is
                  too close to call, which is why a small gap counts as a tie.
                </p>
              )}
              {!artefact.fit.probed && artefact.fit.unconfirmed_reason && (
                // The technical reason the fit test came back empty. It belongs
                // down here and nowhere else: it is raw enough to have shown a
                // student a numpy dtype error once.
                <p>No fit test: {artefact.fit.unconfirmed_reason}</p>
              )}
              {artefact.assumptions.length > 0 && (
                <ul>
                  {artefact.assumptions.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              )}
            </div>
          </details>
        </>
      )}
    </div>
  )
}
