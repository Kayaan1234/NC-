import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { getModelContent } from '../content'
import Message from '../components/Message'
import VerifyNotice from '../components/VerifyNotice'
import { message } from '../train'
import {
  completedRun,
  findActiveRun,
  formatRows,
  matchTopics,
  runsForModel,
  staleFailure,
  verdictPath,
  type BridgeRecent,
  type BridgeRecentLookup,
  type BridgeRun,
  type BridgeRunAccepted,
  type BridgeSpec,
  type BridgeTopic,
} from '../bridge'

// The dataset finder for one model, reached from that model's learn rail. It
// is scoped to a step on purpose: "which data suits this?" only means anything
// once you know which model you are building, and the rail already tells us.
//
// Four things, in the order a student needs them:
//   1. a search box that answers instantly from the cache when it can, and
//      offers a real agent run when it cannot
//   2. whatever check they have running right now
//   3. the topics they looked up themselves, newest first
//   4. a few hand-picked datasets that are known to work for this step
//
// (3) is the half of the page that belongs to them, and it exists because their
// own results can never appear in (4). A live run stores its verdict as a DRAFT
// and the shelf lists PUBLISHED only, so promoting is a curator's deliberate act
// — which means without a list of their own, a finished search had nowhere to
// land at all. It used to vanish: the progress panel unmounts the moment a run
// stops being queued or running, and nothing rendered a succeeded one.
//
// Topics checked by other people are still not listed anywhere. They are
// reachable through the search box, which is the point: the shelf stays short no
// matter how many topics get checked.

function TopicCard({
  topic,
  modelId,
  isNew = false,
}: {
  topic: BridgeTopic
  modelId: string
  isNew?: boolean
}) {
  return (
    <li>
      <Link
        to={verdictPath(modelId, topic.topic_slug)}
        className={isNew ? 'model model--new' : 'model'}
      >
        <div className="model__name">
          {topic.topic_display}
          {isNew && <span className="model__flag">just now</span>}
        </div>
        <div className="model__desc">{topic.summary}</div>
        {(topic.dataset_title || topic.rows) && (
          <div className="model__meta">
            {[topic.dataset_title, formatRows(topic.rows)].filter(Boolean).join(' · ')}
          </div>
        )}
      </Link>
    </li>
  )
}

export default function Bridge() {
  const { user } = useAuth()
  const { modelId = '' } = useParams()

  const [spec, setSpec] = useState<BridgeSpec | null>(null)
  const [featured, setFeatured] = useState<BridgeTopic[]>([])
  const [checked, setChecked] = useState<BridgeTopic[]>([])
  const [recents, setRecents] = useState<BridgeRecent[]>([])
  const [runs, setRuns] = useState<BridgeRun[]>([])
  const [query, setQuery] = useState('')
  const [justFound, setJustFound] = useState<{ slug: string; label: string } | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  // The run whose finish this page is waiting to announce. A ref, not state:
  // the polling interval reads it, and putting it in the dependency array would
  // tear the interval down and rebuild it on every tick.
  const watchedRunId = useRef<string | null>(null)

  const content = getModelContent(modelId)
  const stepName = spec?.display_name ?? content?.name ?? modelId

  // Returns the fresh list as well as storing it. The poll callback needs the
  // runs it just fetched; reading `runs` there would read the closure's stale
  // copy from the render that created the interval.
  const loadRuns = useCallback(async () => {
    const all = await api<BridgeRun[]>('/bridge/runs', { method: 'GET', auth: true })
    const mine = runsForModel(all, modelId)
    setRuns(mine)
    return mine
  }, [modelId])

  // Both lists move together after a search: `recents` gains the topic, and
  // `checked` is what makes the search box say "ready now" for it next time.
  // Refreshing only the first leaves the box unable to find a topic the page is
  // simultaneously displaying.
  const loadFound = useCallback(async () => {
    const [mine, all] = await Promise.all([
      api<BridgeRecent[]>(`/bridge/recent?model_id=${modelId}`, { method: 'GET', auth: true }),
      api<BridgeTopic[]>(`/bridge/topics?model_id=${modelId}`, { method: 'GET', auth: true }),
    ])
    setRecents(mine)
    setChecked(all)
  }, [modelId])

  useEffect(() => {
    if (!user?.verified) {
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const [specs, published] = await Promise.all([
          api<BridgeSpec[]>('/bridge/specs', { method: 'GET', auth: true }),
          api<BridgeTopic[]>(`/bridge/library?model_id=${modelId}`, { method: 'GET', auth: true }),
          loadFound(),
        ])
        if (cancelled) return
        setSpec(specs.find((s) => s.model_id === modelId) ?? null)
        setFeatured(published)
        await loadRuns()
      } catch (err) {
        if (!cancelled) setError(message(err, 'Could not load the dataset finder'))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [user, modelId, loadRuns, loadFound])

  const matches = useMemo(() => matchTopics(checked, query), [checked, query])
  const activeRun = findActiveRun(runs)
  const failedRun = staleFailure(runs)

  // Poll only while a check is in flight, and stop the moment it finishes.
  // Both dependencies are primitives on purpose: activeRun is a fresh object on
  // every poll, so depending on it would tear down and rebuild the interval each
  // time and the timer would never actually elapse.
  const hasActive = !!activeRun
  const stalled = activeRun?.stalled ?? false
  useEffect(() => {
    if (!hasActive) return
    // Back off rather than stop when the queue is not moving. Stopping would
    // mean the page never notices the worker coming back, and a 2s poll against
    // something known to be stuck is just noise in the log.
    const id = setInterval(async () => {
      const fresh = await loadRuns().catch(() => null)
      if (!fresh) return
      // The tick where the wait ends. Without this the section above simply
      // unmounts and the page looks untouched, which is the whole bug.
      const done = completedRun(fresh, watchedRunId.current)
      if (!done) return
      watchedRunId.current = null
      setJustFound({ slug: done.topic_slug, label: done.topic_input })
      loadFound().catch(() => {})
    }, stalled ? 20000 : 2000)
    return () => clearInterval(id)
  }, [hasActive, stalled, loadRuns, loadFound])

  async function onCancel(id: string) {
    setError('')
    try {
      await api(`/bridge/runs/${id}`, { method: 'DELETE', auth: true })
      await loadRuns()
    } catch (err) {
      setError(message(err, 'Could not call off the search'))
    }
  }

  /** Announce a topic that is ready to open, and pull it into the lists. */
  async function announce(slug: string, label: string) {
    setJustFound({ slug, label })
    setQuery('')
    await loadFound()
  }

  async function onSearch(e: React.FormEvent) {
    e.preventDefault()
    const topic = query.trim()
    setError('')
    setBusy(true)
    try {
      // Ask the shelf first. This costs nothing and is deliberately NOT the
      // endpoint that carries RATE_LIMIT_BRIDGE: that limit is 3/hour and its
      // decorator sits outside POST /bridge/runs, so it counts a request before
      // the handler can find out the answer was already cached. Routing free
      // lookups through there made a fourth search in an hour fail with "budget
      // used up" when not one of the four would have spent anything.
      const found = await api<BridgeRecentLookup>('/bridge/recent', {
        method: 'POST',
        auth: true,
        body: { topic, model_id: modelId },
      })
      if (found.exists) {
        await announce(found.topic_slug, topic)
        return
      }

      // A genuine miss, so this one needs an agent run and the hourly limit that
      // guards the spending applies.
      const accepted = await api<BridgeRunAccepted>('/bridge/runs', {
        method: 'POST',
        auth: true,
        body: { topic, model_id: modelId },
      })
      if (accepted.library_hit) {
        // A verdict landed between the two calls — another tab, or someone
        // else's run finishing. Same outcome, no run of our own.
        await announce(accepted.topic_slug, topic)
        return
      }
      watchedRunId.current = accepted.job?.id ?? null
      setJustFound(null)
      setQuery('')
      await loadRuns()
    } catch (err) {
      setError(message(err, 'Could not start the search'))
    } finally {
      setBusy(false)
    }
  }

  if (!user) return null
  if (!user.verified) return <VerifyNotice />

  return (
    <div className="container-app">
      <p className="backlink">
        <Link to={content ? `/training/${modelId}/learn` : `/training/${modelId}`}>
          &larr; {stepName}
        </Link>
      </p>

      <div className="page-header">
        <h1>Find a dataset</h1>
        <p>
          Something you would actually enjoy building with, checked to make sure it suits
          the {stepName.toLowerCase()} you are about to write.
        </p>
      </div>

      {loading && <p className="page-status">Loading...</p>}
      {error && <Message kind="error">{error}</Message>}

      {!loading && (
        <form className="finder" onSubmit={onSearch}>
          <label htmlFor="bridge-topic">What do you want to build with?</label>
          <input
            id="bridge-topic"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="football, birdsong, chess, anything you like"
            maxLength={200}
            autoComplete="off"
          />

          {matches.length > 0 && (
            <div className="finder__matches">
              <span className="finder__label">Already checked</span>
              <ul>
                {matches.slice(0, 5).map((t) => (
                  <li key={t.topic_slug}>
                    <Link to={verdictPath(modelId, t.topic_slug)}>{t.topic_display}</Link>
                    <span className="finder__ready">ready now</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {query.trim().length >= 3 && (
            <div className="finder__go">
              <button type="submit" className="btn-primary" disabled={busy || !!activeRun}>
                {busy ? 'Starting...' : `Search for "${query.trim()}"`}
              </button>
              <span className="finder__hint">
                {activeRun ? 'One search at a time, yours is still running' : 'takes a couple of minutes'}
              </span>
            </div>
          )}
        </form>
      )}

      {activeRun && (
        <div className="section">
          <h2 className="section__title">Looking for {activeRun.topic_input}</h2>
          {activeRun.stalled ? (
            // Saying "starting up" here would be a lie that costs someone an
            // afternoon: nothing is picking this up, and only the server can
            // tell, so say it plainly and offer the way out.
            <>
              <Message kind="info">
                This one has not started. The machine that runs the searches looks like
                it is down, so nothing is working on it right now. It will pick up on its
                own if that changes.
              </Message>
              <button type="button" className="btn-quiet" onClick={() => onCancel(activeRun.id)}>
                Stop waiting
              </button>
            </>
          ) : (
            <ul className="runlog">
              {activeRun.progress.slice(-6).map((event, i) => (
                <li key={`${event.t}-${i}`}>{event.text}</li>
              ))}
              {activeRun.progress.length === 0 && <li>Starting up...</li>}
            </ul>
          )}
        </div>
      )}

      {/* Only 'failed', and only if it is their newest run for this step. A run
          they called off is 'cancelled', and telling them it "stopped early"
          would be reporting their own click back at them. The newest-run test
          matters just as much: /bridge/runs returns their whole history and
          there is no way to clear it, so picking the newest *failure* out of
          that list pinned one bad afternoon above the shelf forever. */}
      {failedRun && (
        <Message kind="error">
          The search for {failedRun.topic_input} stopped early. {failedRun.error}
        </Message>
      )}

      {justFound && (
        <Message kind="ok">
          Found something for {justFound.label}. It is at the top of your recent searches.
          <div className="msg__actions">
            <Link to={verdictPath(modelId, justFound.slug)}>Open it &rarr;</Link>
          </div>
        </Message>
      )}

      {!loading && recents.length > 0 && (
        <div className="section">
          <h2 className="section__title">Your recent searches</h2>
          <ul className="model-list">
            {recents.map((t) => (
              <TopicCard
                key={t.topic_slug}
                topic={t}
                modelId={modelId}
                isNew={t.topic_slug === justFound?.slug}
              />
            ))}
          </ul>
        </div>
      )}

      {!loading && featured.length > 0 && (
        <div className="section">
          <h2 className="section__title">Known to work well here</h2>
          <ul className="model-list">
            {featured.map((t) => (
              <TopicCard key={t.topic_slug} topic={t} modelId={modelId} />
            ))}
          </ul>
        </div>
      )}

      {!loading && featured.length === 0 && recents.length === 0 && !activeRun && (
        <p className="empty">
          No picked-out datasets for this step yet. Search for a topic above and see what turns up.
        </p>
      )}
    </div>
  )
}
