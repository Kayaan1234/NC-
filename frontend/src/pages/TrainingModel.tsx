import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import Message from '../components/Message'
import VerifyNotice from '../components/VerifyNotice'
import { message, type ModelSpec, type ParamSpec } from '../train'

// Config page for one model, reached from the menu at /training. The model id
// comes from the URL (/training/:modelId), so this page is bookmarkable and
// survives a hard refresh — it re-fetches the spec rather than relying on
// navigation state. On a successful queue it returns to the menu, where the new
// job shows up in "Your jobs".
//
// The form is GENERATED from the spec's parameter descriptors, so a new model
// needs no code here: it gets the inputs its registry entry declares, with the
// bounds the server will actually enforce. Adding a new *kind* of parameter is
// the only thing that touches this file (one more branch in Field below).
//
// Route note: the path is /training/:modelId, NOT /train/*, because the API
// prefix is /train and a SPA route under it gets proxied to the backend instead
// of served (see App.tsx / the training-job-pipeline notes).

// The parameter every model happens to key its per-dataset defaults off. Treated
// as a convention, not a requirement: a model with no parameter by this name
// simply never triggers the re-defaulting below.
const DATASET = 'dataset'

type Values = Record<string, string>

// Everything is held as a string: an empty number input is a valid intermediate
// state, and the server validates the real bounds anyway (the min/max attributes
// here are only hints).
function initialValues(model: ModelSpec): Values {
  const values: Values = {}
  for (const p of model.params) values[p.name] = String(p.default)
  return withDatasetDefaults(model, values, values[DATASET])
}

// Overlay the chosen dataset's defaults. This is what makes picking "mnist" fill
// in 15 epochs rather than leaving XOR's 2000 — the binary has the same table in
// its apply_defaults(), but the form always sends every flag, so the server-side
// copy in the registry is the one that gets used.
function withDatasetDefaults(model: ModelSpec, values: Values, dataset: string | undefined): Values {
  const overrides = dataset ? model.dataset_defaults[dataset] : undefined
  if (!overrides) return values
  const next = { ...values }
  for (const [name, value] of Object.entries(overrides)) next[name] = String(value)
  return next
}

function Field({
  param,
  value,
  onChange,
}: {
  param: ParamSpec
  value: string
  onChange: (next: string) => void
}) {
  const id = `tr-${param.name}`
  const common = {
    id,
    value,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => onChange(e.target.value),
    required: true,
  }

  return (
    <div className="field">
      <label htmlFor={id}>{param.label}</label>
      {param.kind === 'choice' && (
        <select {...common}>
          {param.choices.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      )}
      {(param.kind === 'float' || param.kind === 'int') && (
        <input
          {...common}
          type="number"
          // step="any" or the browser rejects 0.05 on an integer-stepped input.
          step={param.kind === 'float' ? 'any' : 1}
          min={param.minimum ?? undefined}
          max={param.maximum ?? undefined}
        />
      )}
      {param.kind === 'int_list' && <input {...common} type="text" placeholder="e.g. 64,32" />}
      {/* The help text used to trail the control inline on the same line, which
          put the bounds of a parameter in the least readable place on the page.
          It's a block hint under the input now. */}
      {param.help && <small className="field__hint">{param.help}</small>}
    </div>
  )
}

function RunForm({ model }: { model: ModelSpec }) {
  const navigate = useNavigate()
  const [values, setValues] = useState<Values>(() => initialValues(model))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function setParam(param: ParamSpec, next: string) {
    setValues((prev) => {
      const updated = { ...prev, [param.name]: next }
      // Switching dataset re-defaults the rest of the form; every other field
      // just updates itself.
      return param.name === DATASET ? withDatasetDefaults(model, updated, next) : updated
    })
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      // Numbers go over as numbers, choices and lists as strings — matching the
      // kinds services/params.py coerces to.
      const body: Record<string, string | number> = {}
      for (const p of model.params) {
        const raw = values[p.name]
        body[p.name] = p.kind === 'float' || p.kind === 'int' ? Number(raw) : raw
      }
      await api(`/train/${model.model_id}/run`, { method: 'POST', auth: true, body })
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
    <>
      <div className="page-header">
        <h1>{model.name}</h1>
        <p>{model.description}</p>
      </div>
      <form className="card form-grid" onSubmit={onSubmit}>
        {model.params.map((p) => (
          <Field
            key={p.name}
            param={p}
            value={values[p.name] ?? ''}
            onChange={(next) => setParam(p, next)}
          />
        ))}
        <div className="form-actions">
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Queuing...' : 'Run training'}
          </button>
        </div>
        <p className="card__note">
          One job at a time. Values outside the listed ranges are rejected by the server.
        </p>
        {error && <Message kind="error">{error}</Message>}
      </form>
    </>
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

  if (!user.verified) return <VerifyNotice />

  return (
    <div className="container-app">
      <p className="backlink">
        <Link to="/training">&larr; All models</Link>
      </p>
      {loading && <p className="page-status">Loading...</p>}
      {error && <Message kind="error">{error}</Message>}
      {!loading && !error && !model && (
        <Message kind="error">That model does not exist.</Message>
      )}
      {/* key: remounting on model change re-seeds the form state from the new
          spec's defaults, instead of carrying the previous model's values over. */}
      {model && <RunForm key={model.model_id} model={model} />}
    </div>
  )
}
