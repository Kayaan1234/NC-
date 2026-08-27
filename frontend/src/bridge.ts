// Shared shapes for the Bridge dataset finder, used by pages/Bridge.tsx (the
// finder, reached from a model's learn rail) and pages/BridgeVerdict.tsx (one
// dataset). Mirrors backend/schemas/bridge.py, so change one and change both.
//
// Nothing here names a step. Both pages read the step from the URL and the
// server describes it, which is the same rule train.ts follows.

export type BridgeSpec = {
  model_id: string
  ordinal: number
  display_name: string
  capability: string
  modality: string
  data_requirement: string
  has_probe: boolean
  available: boolean
}

export type ProgressEvent = { t: string; text: string }

export type BridgeRun = {
  id: string
  topic_input: string
  topic_slug: string
  model_id: string
  status: string
  stage: string | null
  progress: ProgressEvent[]
  created_at: string
  started_at: string | null
  finished_at: string | null
  error: string | null
  queue_position: number | null
  verdict_ready: boolean
  // The queue this run is sitting in has stopped moving, so nothing is working
  // on it. Derived by the server on every read, never stored.
  stalled: boolean
}

export type BridgeRunAccepted = {
  library_hit: boolean
  topic_slug: string
  model_id: string
  job: BridgeRun | null
}

// One row of the finder: enough to draw a card without fetching the artefact.
export type BridgeTopic = {
  topic_slug: string
  topic_display: string
  model_id: string
  verdict_value: string
  summary: string
  dataset_title: string | null
  rows: number | null
  published: boolean
}

// A topic this student looked up themselves, with when they last did it.
export type BridgeRecent = BridgeTopic & { searched_at: string }

// POST /bridge/recent: did the shelf already have this, and what slug did the
// server normalise it to? `exists: false` means nothing was recorded and the
// caller should fall through to POST /bridge/runs.
export type BridgeRecentLookup = { topic_slug: string; exists: boolean }

// How many of their own searches the finder shows. Mirrors RECENT_SEARCH_LIMIT
// in backend/models/Bridge.py, which is the one that actually evicts.
export const RECENT_LIMIT = 3

// The stored artefact. Typed loosely on purpose: the page renders what is
// present rather than demanding every optional section, and the parts it does
// not show (search evidence, per-seed numbers) still travel for the details
// disclosure at the bottom.
export type VerdictArtefact = {
  verdict: string
  summary: string
  topic: string
  model_id: string
  display_name: string
  capability: string
  evidence: {
    queries: string[]
    candidates_considered: number
    rejections: Record<
      string,
      { count: number; examples: { dataset_id: string; source: string; reason: string }[] }
    >
    replan_rounds: number
    not_inspected?: number
  }
  dataset: null | {
    source: string
    dataset_id: string
    url: string
    title: string
    license: string | null
    scale: Record<string, unknown>
  }
  fit: {
    probed: boolean
    outcome?: string
    reason?: string
    metric?: string
    means?: Record<string, number>
    noise_band?: number
    rows_used?: number
    unconfirmed_reason?: string
  }
  difficulty: null | { tier: number }
  api_path:
    | null
    | {
        name: string
        docs_url: string
        auth: string
        reachable: boolean
        rate_limit_per_day: number
        records_needed: number
        estimated_collection_days: number
        terms_note: string
      }[]
  nearest_domain: null | {
    dataset_id: string
    url: string | null
    title: string | null
    similarity: number
  }[]
  definition_of_done: string
  inherited_from: string | null
  assumptions: string[]
}

export type BridgeVerdictRecord = {
  topic_slug: string
  model_id: string
  topic_display: string
  status: string
  verdict: VerdictArtefact
  last_verified: string
  // Plain-language projections computed by the server (services/bridge/plain.py).
  plain_fit: string | null
  plain_license: string | null
  plain_difficulty: string | null
  plain_done: string | null
  step_name: string | null
}

// The headline a student reads first. Phrased as an answer to "can I build my
// project with this?", not as a classification label.
export const VERDICT_PRESENTATION: Record<
  string,
  { label: string; tone: 'ok' | 'warn' | 'err' }
> = {
  buildable_now: { label: 'Good fit, ready to build', tone: 'ok' },
  buildable_after_collection: { label: 'You would need to gather the data first', tone: 'warn' },
  not_at_this_step: { label: 'Real data, but not for this model', tone: 'warn' },
  not_at_hobby_scale: { label: 'Nothing usable found for this one', tone: 'err' },
}

export function bridgePath(modelId: string): string {
  return `/training/${modelId}/bridge`
}

export function verdictPath(modelId: string, topicSlug: string): string {
  return `/training/${modelId}/bridge/${topicSlug}`
}

// Cheap client-side match for the finder's search box. The checked-topic list
// is small and fetched once, so filtering as the student types costs nothing
// and beats a request per keystroke.
export function matchTopics(topics: BridgeTopic[], query: string): BridgeTopic[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return []
  return topics.filter(
    (t) =>
      t.topic_display.toLowerCase().includes(needle) ||
      t.topic_slug.includes(needle.replace(/\s+/g, '-')),
  )
}

export function formatRows(rows: number | null | undefined): string {
  return typeof rows === 'number' ? `${rows.toLocaleString()} rows` : ''
}

// The run-list decisions the finder makes, kept here rather than inline in the
// component because vitest runs with no DOM — a helper in this file can be
// tested and the same logic inside Bridge.tsx cannot.

/** Runs belonging to one step. GET /bridge/runs returns every step's. */
export function runsForModel(runs: BridgeRun[], modelId: string): BridgeRun[] {
  return runs.filter((r) => r.model_id === modelId)
}

const ACTIVE_STATUSES = new Set(['queued', 'running'])

/** The check that is in flight right now, if any. */
export function findActiveRun(runs: BridgeRun[]): BridgeRun | null {
  return runs.find((r) => ACTIVE_STATUSES.has(r.status)) ?? null
}

/**
 * The run we were watching, but only once it has a verdict to open.
 *
 * `verdict_ready` rather than `status === 'succeeded'`: the server computes it,
 * and it is the field that answers the question the page is actually asking —
 * is there something at verdictPath() yet. It shipped in the API from the start
 * and nothing had ever read it.
 */
export function completedRun(runs: BridgeRun[], watchedId: string | null): BridgeRun | null {
  if (!watchedId) return null
  const run = runs.find((r) => r.id === watchedId)
  return run && run.verdict_ready ? run : null
}

/**
 * A failure worth showing: the most recent run for this step, and only if it
 * failed.
 *
 * GET /bridge/runs returns a student's whole history, newest first, with no
 * status filter and no way to clear it. Picking the newest *failure* out of that
 * list — which is what this page used to do — pins the first search that ever
 * went wrong above the shelf on every visit thereafter. Reading position 0
 * instead means a later search, successful or still running, retires it.
 */
export function staleFailure(runs: BridgeRun[]): BridgeRun | null {
  const newest = runs[0]
  return newest && newest.status === 'failed' ? newest : null
}
