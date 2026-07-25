import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, downloadFile } from '../api'
import { useAuth } from '../auth'
import { hasContent } from '../content'
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

function ModelCard({ model }: { model: ModelSpec }) {
  // Models with an authored explanation open the learn flow first; models without
  // one link straight to training, as before. A model gains its learn flow the
  // moment its content is registered in content/index.ts — nothing here changes.
  const to = hasContent(model.model_id)
    ? `/training/${model.model_id}/learn`
    : `/training/${model.model_id}`
  return (
    <li>
      <Link to={to}>{model.name}</Link>
      <br />
      <small>{model.description}</small>
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

  return (
    <li>
      {job.model_id} / {dataset} — {job.status}
      {job.status === 'queued' && job.queue_position !== null && ` (position ${job.queue_position})`}
      {summary && ` — ${summary}`}
      {job.error && ` — ${job.error}`}
      {job.report_available && (
        <>
          {' '}
          <button type="button" onClick={onDownload} disabled={busy}>
            {busy ? 'Downloading...' : 'Download report'}
          </button>
        </>
      )}
      {error && <span> {error}</span>}
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
  useEffect(() => {
    if (!user?.verified) {
      setLoading(false)
      return
    }
    ;(async () => {
      try {
        setModels(await api<ModelSpec[]>('/train/models', { method: 'GET', auth: true }))
        await loadJobs()
      } catch (err) {
        setError(message(err, 'Could not load training'))
      } finally {
        setLoading(false)
      }
    })()
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

  if (!user.verified) {
    return (
      <div>
        <h1>Training</h1>
        <p>Verify your email to run training jobs.</p>
        <p>
          <Link to="/">Home</Link>
        </p>
      </div>
    )
  }

  return (
    <div>
      <h1>Training</h1>
      {loading && <p>Loading...</p>}
      {error && <p>{error}</p>}

      <h2>Models</h2>
      {!loading && models.length === 0 ? (
        <p>No models are available to train yet.</p>
      ) : (
        <ul>
          {models.map((m) => (
            <ModelCard key={m.model_id} model={m} />
          ))}
        </ul>
      )}

      <hr />
      <h2>Your jobs</h2>
      {jobs.length === 0 ? (
        <p>No jobs yet.</p>
      ) : (
        <>
          <ul>
            {jobs.map((j) => (
              <JobRow key={j.id} job={j} spec={specs.get(j.model_id)} />
            ))}
          </ul>
          {/* Only offered when there's something clearable — an active job is
              never deleted, so a list of only queued/running jobs shows no button. */}
          {jobs.some((j) => !ACTIVE.has(j.status)) && (
            <button type="button" onClick={clearFinished} disabled={clearing}>
              {clearing ? 'Clearing...' : 'Clear finished jobs'}
            </button>
          )}
        </>
      )}
      <p>
        <Link to="/">Home</Link>
      </p>
    </div>
  )
}
