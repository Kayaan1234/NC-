import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { DashboardData, RungProgress } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import RoadmapNeuron from '../components/RoadmapNeuron'

export default function Dashboard() {
  const { user } = useAuth()
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true

    // Dev affordance: /dashboard?mock=1 renders a richer roadmap so the lit-node
    // and lit-pathway states are visible while only rung 0 is really seeded.
    // `import.meta.env.DEV` is statically false in production, so this whole
    // branch — mock data and all — is dead-code-eliminated from the prod bundle.
    // (The mock is built INSIDE the branch on purpose so nothing survives DCE.)
    if (import.meta.env.DEV && new URLSearchParams(window.location.search).has('mock')) {
      const m = (
        number: number,
        slug: string,
        title: string,
        status: RungProgress['status'],
        done: number,
        total: number,
      ): RungProgress => ({
        id: `mock-${number}`,
        number,
        slug,
        title,
        status,
        exercises_completed: done,
        exercises_total: total,
      })
      setData({
        current_rung_number: 5,
        rungs: [
          m(0, 'the-single-neuron', 'The single neuron', 'completed', 1, 1),
          m(1, 'mlp', 'Multilayer perceptron', 'completed', 3, 3),
          m(2, 'autodiff', 'The autodiff engine', 'completed', 2, 2),
          m(3, 'training', 'Making training work', 'completed', 2, 2),
          m(4, 'cnn', 'Convolutional network', 'unlocked', 0, 2),
          m(5, 'rnn', 'Recurrent network', 'unlocked', 1, 3),
          m(6, 'lstm', 'LSTM & GRU', 'locked', 0, 0),
          m(7, 'seq2seq', 'Sequence to sequence', 'locked', 0, 0),
          m(8, 'attention', 'Attention', 'locked', 0, 0),
          m(9, 'transformer', 'Transformer', 'locked', 0, 0),
        ],
      })
      setLoading(false)
      return
    }

    api
      .dashboard()
      .then((d) => {
        if (alive) {
          setData(d)
          setLoading(false)
        }
      })
      .catch((e) => {
        if (!alive) return
        setError(e instanceof ApiError ? e.message : 'Could not load your roadmap.')
        setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  if (!user) return null

  const total = data?.rungs.length ?? 0
  const unlocked = data ? data.rungs.filter((r) => r.status !== 'locked').length : 0

  return (
    <div className="dash">
      <p className="eyebrow mono">your roadmap</p>
      <h1>
        From a <span className="grad-fwd">single neuron</span> to a transformer.
      </h1>
      <p className="lede">
        Ten rungs, each built in C++ from scratch.{' '}
        {total > 0 && (
          <>
            <span className="mono rn-count">
              {unlocked}/{total}
            </span>{' '}
            unlocked — light up the next by finishing the one before it.
          </>
        )}
      </p>

      {loading && <div className="page-loading mono">tracing the roadmap…</div>}
      {error && (
        <div className="alert alert-error" role="alert">
          {error}
        </div>
      )}
      {data && <RoadmapNeuron rungs={data.rungs} currentRungNumber={data.current_rung_number} />}

      <p className="auth-alt dash-account-link">
        Manage your account in <Link to="/account">account settings</Link>.
      </p>
    </div>
  )
}
