import { Link } from 'react-router-dom'
import NeuralNetAnimation from '../components/NeuralNetAnimation'
import { useAuth } from '../auth/AuthContext'

const LADDER = [
  {
    rung: 'RUNG 1',
    name: 'the one-liner',
    sub: 'what you call',
    code: 'MLPClassifier().fit(X, y)',
  },
  {
    rung: 'RUNG 2',
    name: "what's underneath",
    sub: 'what it does',
    code: 'forward · autograd · optimiser step',
  },
  {
    rung: 'RUNG 3',
    name: 'the real thing',
    sub: 'how it’s built',
    code: 'matrix loops · memory · SIMD — in C++',
  },
]

export default function Landing() {
  const { user } = useAuth()

  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow mono">neural networks, from a single neuron up</p>
          <h1>
            Watch a network <span className="grad-fwd">think forward</span> and{' '}
            <span className="grad-bwd">learn backward</span>.
          </h1>
          <p className="lede">
            Most courses teach the maths and stop. I built every architecture in C++ by
            hand and then turned that hard-won understanding into a tutorial, so that you go from using AI to knowing AI.
          </p>
          <div className="hero-cta">
            {user ? (
              <Link to="/dashboard" className="btn btn-primary">
                Go to your dashboard
              </Link>
            ) : (
              <>
                <Link to="/register" className="btn btn-primary">
                  Start building
                </Link>
                <Link to="/login" className="btn btn-ghost">
                  Log in
                </Link>
              </>
            )}
          </div>
        </div>

        <div className="hero-viz card">
          <NeuralNetAnimation />
        </div>
      </section>

      <section className="ladder">
        <p className="section-kicker mono">the abstraction ladder</p>
        <h2>One line at the top is hundreds of lines at the bottom.</h2>
        <div className="ladder-grid">
          {LADDER.map((r) => (
            <div key={r.rung} className="ladder-card card">
              <div className="ladder-head">
                <span className="ladder-rung mono">{r.rung}</span>
                <span className="ladder-sub mono">{r.sub}</span>
              </div>
              <h3>{r.name}</h3>
              <code className="ladder-code">{r.code}</code>
            </div>
          ))}
        </div>
        <p className="ladder-note">
          The interesting part is the part nobody shows: translating the maths into unabstracted, optimised code, and{' '}
          <em>why</em> the fast version is fast.
        </p>
      </section>
    </div>
  )
}
