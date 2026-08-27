// bridge.ts — the pure decisions behind the dataset finder.
//
// The suite runs with `environment: 'node'` and no jsdom, so Bridge.tsx itself
// cannot be rendered here. That is exactly why these helpers live in bridge.ts
// rather than inline in the component: the run-list logic is where the finder's
// bugs have actually been, and this is the only place it can be pinned down.

import { describe, expect, it } from 'vitest'

import {
  RECENT_LIMIT,
  completedRun,
  findActiveRun,
  formatRows,
  matchTopics,
  runsForModel,
  staleFailure,
  verdictPath,
  type BridgeRun,
  type BridgeTopic,
} from './bridge'

function run(overrides: Partial<BridgeRun> = {}): BridgeRun {
  return {
    id: 'r1',
    topic_input: 'wine quality',
    topic_slug: 'wine-quality',
    model_id: 'step1',
    status: 'queued',
    stage: null,
    progress: [],
    created_at: '2026-08-21T12:00:00',
    started_at: null,
    finished_at: null,
    error: null,
    queue_position: 0,
    verdict_ready: false,
    stalled: false,
    ...overrides,
  }
}

function topic(overrides: Partial<BridgeTopic> = {}): BridgeTopic {
  return {
    topic_slug: 'wine-quality',
    topic_display: 'Wine quality',
    model_id: 'step1',
    verdict_value: 'buildable_now',
    summary: 'a fine dataset exists',
    dataset_title: null,
    rows: null,
    published: false,
    ...overrides,
  }
}

describe('runsForModel', () => {
  it('keeps only the step being looked at', () => {
    // GET /bridge/runs returns every step's runs; the finder is scoped to one.
    const runs = [run({ id: 'a', model_id: 'step0' }), run({ id: 'b', model_id: 'step1' })]
    expect(runsForModel(runs, 'step1').map((r) => r.id)).toEqual(['b'])
  })
})

describe('findActiveRun', () => {
  it('matches queued and running', () => {
    expect(findActiveRun([run({ status: 'queued' })])?.id).toBe('r1')
    expect(findActiveRun([run({ status: 'running' })])?.id).toBe('r1')
  })

  it('matches no terminal state', () => {
    for (const status of ['succeeded', 'failed', 'cancelled']) {
      expect(findActiveRun([run({ status })])).toBeNull()
    }
  })
})

describe('completedRun', () => {
  it('waits for verdict_ready, not merely for the run to leave the queue', () => {
    // The distinction the page depends on: there is no point announcing a
    // result before there is something at verdictPath() to open.
    const runs = [run({ id: 'a', status: 'succeeded', verdict_ready: false })]
    expect(completedRun(runs, 'a')).toBeNull()
  })

  it('returns the watched run once its verdict exists', () => {
    const runs = [run({ id: 'a', status: 'succeeded', verdict_ready: true })]
    expect(completedRun(runs, 'a')?.id).toBe('a')
  })

  it('ignores a finished run nobody was watching', () => {
    // Load-bearing: without the id check, opening the finder while an old run
    // sits in the history would fire the success banner for a search the
    // student made days ago.
    const runs = [run({ id: 'old', status: 'succeeded', verdict_ready: true })]
    expect(completedRun(runs, 'watched')).toBeNull()
  })

  it('returns nothing when no run is being watched', () => {
    const runs = [run({ id: 'a', status: 'succeeded', verdict_ready: true })]
    expect(completedRun(runs, null)).toBeNull()
  })
})

describe('staleFailure', () => {
  it('reports a failure that is the newest run', () => {
    expect(staleFailure([run({ status: 'failed', error: 'boom' })])?.error).toBe('boom')
  })

  it('retires a failure once a newer search exists', () => {
    // The old code picked the newest *failure* out of the whole history, which
    // pinned one bad afternoon above the shelf on every visit forever after.
    // /bridge/runs is created_at DESC and there is no way to clear it.
    const runs = [run({ id: 'new', status: 'succeeded' }), run({ id: 'old', status: 'failed' })]
    expect(staleFailure(runs)).toBeNull()
  })

  it('stays quiet while a newer run is still going', () => {
    const runs = [run({ id: 'new', status: 'running' }), run({ id: 'old', status: 'failed' })]
    expect(staleFailure(runs)).toBeNull()
  })

  it('says nothing about a run the student called off', () => {
    // 'cancelled' is their own click; reporting it back as a failure would be
    // telling them something went wrong when they stopped it themselves.
    expect(staleFailure([run({ status: 'cancelled' })])).toBeNull()
  })

  it('copes with no runs at all', () => {
    expect(staleFailure([])).toBeNull()
  })
})

describe('matchTopics', () => {
  it('matches on the display name, case-insensitively', () => {
    expect(matchTopics([topic()], 'WINE').map((t) => t.topic_slug)).toEqual(['wine-quality'])
  })

  it('matches a spaced query against the hyphenated slug', () => {
    expect(matchTopics([topic()], 'wine qual')).toHaveLength(1)
  })

  it('returns nothing for an empty query, rather than everything', () => {
    // The finder renders this list directly, so returning all topics on an
    // empty box would dump the whole library under the input.
    expect(matchTopics([topic()], '   ')).toEqual([])
  })
})

describe('formatRows', () => {
  it('groups thousands and names the unit', () => {
    expect(formatRows(12345)).toBe('12,345 rows')
  })

  it('is empty rather than "0 rows" when the count is unknown', () => {
    expect(formatRows(null)).toBe('')
    expect(formatRows(undefined)).toBe('')
  })

  it('still reports a genuine zero', () => {
    expect(formatRows(0)).toBe('0 rows')
  })
})

describe('verdictPath', () => {
  it('sits under /training, never /train', () => {
    // /train is the API prefix; a SPA route shadowing it gets proxied to the
    // backend on a full-page load (see App.tsx).
    expect(verdictPath('step1', 'wine-quality')).toBe('/training/step1/bridge/wine-quality')
  })
})

describe('RECENT_LIMIT', () => {
  it('mirrors the server, which is the one that actually evicts', () => {
    // RECENT_SEARCH_LIMIT in backend/models/Bridge.py. The client never trims
    // the list itself, so a mismatch here would only mislead a reader — but it
    // would mislead them badly.
    expect(RECENT_LIMIT).toBe(3)
  })
})
