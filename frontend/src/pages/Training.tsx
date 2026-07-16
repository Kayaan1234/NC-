import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, downloadFile } from '../api'
import { useAuth } from '../auth'

// Mirrors the backend ModelSpecResponse / JobStatusResponse (see routers/train.py).
type ModelParams = {
  datasets: string[]
  lr_min: number
  lr_max: number
  lr_default: number
  epochs_max: number
  epochs_default: number
}

type ModelSpec = {
  model_id: string
  name: string
  description: string
  params: ModelParams
}

type Job = {
  id: string
  model_id: string
  params: Record<string, unknown>
  status: string
  result: Record<string, unknown> | null
  error: string | null
  queue_position: number | null
  report_available: boolean
}

// The two non-terminal states. While a job is in one of these it still holds the
// user's single slot, and it's worth polling.
const ACTIVE = new Set(['queued', 'running'])

function message(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

function accuracy(job: Job): string {
  const acc = job.result?.final_accuracy
  return typeof acc === 'number' ? `accuracy ${(acc * 100).toFixed(1)}%` : ''
}

function RunForm({ model, onQueued }: { model: ModelSpec; onQueued: () => void }) {
  const p = model.params
  // Kept as strings: an empty number input is a valid intermediate state, and the
  // server validates the real bounds anyway (the min/max here are only hints).
  const [dataset, setDataset] = useState(p.datasets[0])
  const [lr, setLr] = useState(String(p.lr_default))
  const [epochs, setEpochs] = useState(String(p.epochs_default))
  const [seed, setSeed] = useState('42')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api(`/train/${model.model_id}/run`, {
        method: 'POST',
        auth: true,
        body: { dataset, lr: Number(lr), epochs: Number(epochs), seed: Number(seed) },
      })
      onQueued()
    } catch (err) {
      // 409 (already have a job), 503 (disabled), 422 (bad param) all arrive here
      // as the server's message.
      setError(message(err, 'Could not queue training job'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <h2>{model.name}</h2>
      <p>{model.description}</p>
      <div>
        <label htmlFor="tr-dataset">Dataset</label>
        <br />
        <select id="tr-dataset" value={dataset} onChange={(e) => setDataset(e.target.value)}>
          {p.datasets.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="tr-lr">Learning rate</label>
        <br />
        <input
          id="tr-lr"
          type="number"
          step="any"
          min={p.lr_min}
          max={p.lr_max}
          value={lr}
          onChange={(e) => setLr(e.target.value)}
          required
        />
      </div>
      <div>
        <label htmlFor="tr-epochs">Epochs</label>
        <br />
        <input
          id="tr-epochs"
          type="number"
          min={1}
          max={p.epochs_max}
          value={epochs}
          onChange={(e) => setEpochs(e.target.value)}
          required
        />
      </div>
      <div>
        <label htmlFor="tr-seed">Seed</label>
        <br />
        <input
          id="tr-seed"
          type="number"
          min={0}
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          required
        />
      </div>
      <button type="submit" disabled={busy}>
        {busy ? 'Queuing...' : 'Run training'}
      </button>
      <p>
        <small>
          One job at a time. lr {p.lr_min}–{p.lr_max}, up to {p.epochs_max} epochs.
        </small>
      </p>
      {error && <p>{error}</p>}
    </form>
  )
}

function JobRow({ job }: { job: Job }) {
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

  return (
    <li>
      {job.model_id} / {dataset} — {job.status}
      {job.status === 'queued' && job.queue_position !== null && ` (position ${job.queue_position})`}
      {accuracy(job) && ` — ${accuracy(job)}`}
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
  const [selected, setSelected] = useState('')
  const [jobs, setJobs] = useState<Job[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [clearing, setClearing] = useState(false)

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
        const ms = await api<ModelSpec[]>('/train/models', { method: 'GET', auth: true })
        setModels(ms)
        if (ms.length) setSelected(ms[0].model_id)
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

  const model = models.find((m) => m.model_id === selected)

  return (
    <div>
      <h1>Training</h1>
      {loading && <p>Loading...</p>}
      {error && <p>{error}</p>}
      {models.length > 1 && (
        <div>
          <label htmlFor="tr-model">Model</label>{' '}
          <select id="tr-model" value={selected} onChange={(e) => setSelected(e.target.value)}>
            {models.map((m) => (
              <option key={m.model_id} value={m.model_id}>
                {m.name}
              </option>
            ))}
          </select>
        </div>
      )}
      {model && <RunForm model={model} onQueued={loadJobs} />}
      <hr />
      <h2>Your jobs</h2>
      {jobs.length === 0 ? (
        <p>No jobs yet.</p>
      ) : (
        <>
          <ul>
            {jobs.map((j) => (
              <JobRow key={j.id} job={j} />
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
