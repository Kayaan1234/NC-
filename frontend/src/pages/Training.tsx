import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, downloadFile } from '../api'
import { useAuth } from '../auth'
import { hasContent } from '../content'
import Message from '../components/Message'
import VerifyNotice from '../components/VerifyNotice'
import { ACTIVE, message, summarise, type Job, type ModelSpec } from '../train'

// The training menu: the intermediate page between Home and a model's config
// form. It lists the models available to train (each links to its own page at
// /training/:modelId) and shows the user's job history, which is cross-model
// (one active slot per user), so it belongs on the hub rather than any one
// model's page.
//
// Job rows are rendered from the model's own result_fields (see train.ts), not
// from any hardcoded key: a single neuron reports one accuracy, an MLP reports
// train and test accuracy plus its topology, and neither is special-cased here.

// The four states the backend emits. Anything else still renders — with the
// neutral grey treatment — rather than dropping the row.
const KNOWN_STATUSES = new Set(['queued', 'running', 'succeeded', 'failed'])

function ModelCard({ model }: { model: ModelSpec }) {
  // Models with an authored explanation open the learn flow first; models without
  // one link straight to training, as before. A model gains its learn flow the
  // moment its content is registered in content/index.ts — nothing here changes.
  const to = hasContent(model.model_id)
    ? `/training/${model.model_id}/learn`
    : `/training/${model.model_id}`
  return (
    <li>
      <Link to={to} className="model">
        <div className="model__name">{model.name}</div>
        <div className="model__desc">{model.description}</div>
      </Link>
    </li>
  )
}

function JobRow({ job, spec }: { job: Job; spec: ModelSpec | undefined }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onDownload() {
    setError('')
    setBusy(true)
    try {
      await downloadFile(
        `/train/jobs/${job.id}/report`,
        `training-${job.model_id}-${job.id.slice(0, 8)}.txt`,
      )
    } catch (err) {
      setError(message(err, 'Could not download report'))
    } finally {
      setBusy(false)
    }
  }

  const dataset = typeof job.params.dataset === 'string' ? job.params.dataset : '?'
  // Empty for a job whose model has since left the registry — the row still
  // renders, and its report is still downloadable.
  const summary = summarise(job, spec)
  const statusClass = KNOWN_STATUSES.has(job.status) ? job.status : 'unknown'

  // A row, not a sentence. The old version ran identity, status, metrics and the
  // error together into one em-dash-separated line, so scanning a list of jobs
  // meant reading each one. Aligned columns mean the status column can be read
  // straight down. There is deliberately no progress indicator for `running`:
  // the API carries no epoch or percentage, only the status itself.
  return (
    <li className="job">
      <div className="job__row">
        <span className="job__name">
          {job.model_id} / {dataset}
        </span>
        <span className={`status status--${statusClass}`}>
          {job.status}
          {job.status === 'queued' && job.queue_position !== null && (
            <span className="status__note"> position {job.queue_position}</span>
          )}
        </span>
        <span className="job__meta">{summary}</span>
        <span className="job__action">
          {job.report_available && (
            <button type="button" className="btn-quiet" onClick={onDownload} disabled={busy}>
              {busy ? 'Downloading...' : 'report'}
            </button>
          )}
        </span>
      </div>
      {/* A failure reason is a paragraph, not a table cell — it gets its own line
          rather than being appended to the row and stretching the grid. */}
      {job.error && <Message kind="error">{job.error}</Message>}
      {error && <Message kind="error">{error}</Message>}
    </li>
  )
}

export default function Training() {
  const { user } = useAuth()
  const [models, setModels] = useState<ModelSpec[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [clearing, setClearing] = useState(false)

  // Jobs are cross-model, so each row needs its own model's spec to know how to
  // render the run's numbers.
  const specs = useMemo(() => new Map(models.map((m) => [m.model_id, m])), [models])

  const loadJobs = useCallback(async () => {
    setJobs(await api<Job[]>('/train/jobs', { method: 'GET', auth: true }))
  }, [])

  async function clearFinished() {
    setError('')
    setClearing(true)
    try {
      // Server deletes only terminal jobs; an active job is left in place.
      await api('/train/jobs', { method: 'DELETE', auth: true })
      await loadJobs()
    } catch (err) {
      setError(message(err, 'Could not clear jobs'))
    } finally {
      setClearing(false)
    }
  }

  // Every /train route requires a verified email (403 otherwise), so there's
  // nothing to fetch for an unverified user — skip straight to the notice below.
  // The guard belongs here in the effect, NOT inside loadJobs: loadJobs is shared
  // with clearFinished() and with the 2-second poll below, and a cancelled flag
  // living inside it would silence those too — the poll would stop updating the
  // moment this effect re-ran.
  useEffect(() => {
    if (!user?.verified) {
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const models = await api<ModelSpec[]>('/train/models', { method: 'GET', auth: true })
        if (cancelled) return
        setModels(models)
        await loadJobs()
      } catch (err) {
        if (!cancelled) setError(message(err, 'Could not load training'))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [user, loadJobs])

  // Poll only while something is in flight; the interval clears itself the moment
  // the last active job reaches a terminal state.
  const hasActive = jobs.some((j) => ACTIVE.has(j.status))
  useEffect(() => {
    if (!hasActive) return
    const id = setInterval(() => {
      loadJobs().catch(() => {})
    }, 2000)
    return () => clearInterval(id)
  }, [hasActive, loadJobs])

  if (!user) return null

  if (!user.verified) return <VerifyNotice />

  return (
    <div className="container-app">
      <div className="page-header">
        <h1>Training</h1>
        <p>Pick a model, read how it works, then set it running. One job at a time.</p>
      </div>

      {loading && <p className="page-status">Loading...</p>}
      {error && <Message kind="error">{error}</Message>}

      <div className="section">
        <h2 className="section__title">Models</h2>
        {!loading && models.length === 0 ? (
          <p className="empty">Nothing available to train just yet.</p>
        ) : (
          <ul className="model-list">
            {models.map((m) => (
              <ModelCard key={m.model_id} model={m} />
            ))}
          </ul>
        )}
      </div>

      <div className="section">
        <h2 className="section__title">Your jobs</h2>
        {jobs.length === 0 ? (
          <p className="empty">No jobs yet.</p>
        ) : (
          <>
            <ul className="job-list">
              {jobs.map((j) => (
                <JobRow key={j.id} job={j} spec={specs.get(j.model_id)} />
              ))}
            </ul>
            {/* Only offered when there's something clearable — an active job is
                never deleted, so a list of only queued/running jobs shows no button. */}
            {jobs.some((j) => !ACTIVE.has(j.status)) && (
              <div className="form-actions">
                <button type="button" className="btn-quiet" onClick={clearFinished} disabled={clearing}>
                  {clearing ? 'Clearing...' : 'Clear finished jobs'}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
