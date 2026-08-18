import { Link } from 'react-router-dom'
import NeuronDemo from '../components/NeuronDemo'

// What a logged-out visitor sees at /. Before this existed every URL a stranger
// typed redirected to the login form, so the site asked for an email address
// before saying what it was.
//
// The page opens with the product's own output rather than a headline: the demo
// is a real neuron training in the browser, and it is running before the visitor
// does anything. Everything else on the page is deliberately quiet so that lands.

// The ladder from neural_computing_cpp_roadmap.md. `available` tracks
// backend/services/registry.py — step0 and step1 are registered and both have a
// main.cpp, so both genuinely train today. The rest are the roadmap and are
// labelled as such: nothing here should read as a thing you can click.
const RUNGS: { n: number; name: string; available?: true }[] = [
  { n: 0, name: 'Single neuron', available: true },
  { n: 1, name: 'Multilayer perceptron', available: true },
  { n: 2, name: 'Autodiff engine' },
  { n: 3, name: 'Training that works' },
  { n: 4, name: 'Convolutional network' },
  { n: 5, name: 'Recurrent network' },
  { n: 6, name: 'LSTM and GRU' },
  { n: 7, name: 'Sequence-to-sequence' },
  { n: 8, name: 'Attention' },
  { n: 9, name: 'Transformer' },
]

export default function Landing() {
  return (
    <div className="container-app">
      <div className="page-header">
        <h1>NC++</h1>
        <p>
          Neural networks built from scratch in C++, one rung at a time. Read how each one
          works, then go and run it yourself.
        </p>
      </div>

      <NeuronDemo />

      <p className="demo__note">
        That is a real single neuron, and it just trained itself in your browser while you were
        reading this. It is the same arithmetic as <code>logistic_regression.hpp</code>, which you
        can go through line by line. Sign in and the very same model compiles and runs as actual
        C++ on a worker, with a report to take away at the end.
      </p>

      <div className="section">
        <h2 className="section__title">The ladder</h2>
        <ul className="rungs">
          {RUNGS.map((r) => (
            <li key={r.n} className="rung">
              <span className="rung__n">{r.n}</span>
              <span className="rung__name">{r.name}</span>
              <span
                className={
                  r.available ? 'status status--succeeded' : 'status status--queued'
                }
              >
                {r.available ? 'available' : 'planned'}
              </span>
            </li>
          ))}
        </ul>
        <p className="rungs__note">
          Each rung builds on the one below it, and every one of them exists because the rung
          underneath ran out of road. A single neuron cannot solve XOR, so Rung 1 adds a hidden
          layer. Writing backprop out by hand stops scaling, so Rung 2 automates it.
        </p>
      </div>

      <div className="cta-row">
        <Link to="/register" className="cta">
          Create an account
        </Link>
        <Link to="/login">Log in</Link>
      </div>
    </div>
  )
}
