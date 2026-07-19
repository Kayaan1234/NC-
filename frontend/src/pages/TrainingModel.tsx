import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { message, type ModelSpec } from '../train'

// Config page for one model, reached from the menu at /training. The model id
// comes from the URL (/training/:modelId), so this page is bookmarkable and
// survives a hard refresh — it re-fetches the spec rather than relying on
// navigation state. On a successful queue it returns to the menu, where the new
// job shows up in "Your jobs".
//
// Route note: the path is /training/:modelId, NOT /train/*, because the API
// prefix is /train and a SPA route under it gets proxied to the backend instead
// of served (see App.tsx / the training-job-pipeline notes).

function RunForm({ model }: { model: ModelSpec }) {
  const navigate = useNavigate()
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
      // Back to the menu so the just-queued job appears in "Your jobs" and starts
      // polling there.
      navigate('/training')
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

export default function TrainingModel() {
  const { user } = useAuth()
  const { modelId } = useParams()
  const [model, setModel] = useState<ModelSpec | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  // Every /train route requires a verified email (403 otherwise), so skip the
  // fetch for an unverified user and show the same notice the menu does.
  useEffect(() => {
    if (!user?.verified) {
      setLoading(false)
      return
    }
    ;(async () => {
      try {
        const models = await api<ModelSpec[]>('/train/models', { method: 'GET', auth: true })
        setModel(models.find((m) => m.model_id === modelId) ?? null)
      } catch (err) {
        setError(message(err, 'Could not load model'))
      } finally {
        setLoading(false)
      }
    })()
  }, [user, modelId])

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
      <p>
        <Link to="/training">← All models</Link>
      </p>
      {loading && <p>Loading...</p>}
      {error && <p>{error}</p>}
      {!loading && !error && !model && <p>That model does not exist.</p>}
      {model && <RunForm model={model} />}
    </div>
  )
}
