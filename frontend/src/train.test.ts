// train.ts — the pure formatting layer between a finished job and the screen.
//
// formatResult's typeof guard is the reason this file exists. The C++ drivers
// print explicit JSON nulls (XOR has no test split, and a diverged run nulls its
// loss and accuracy). `null * 100` is 0 in JavaScript, so without the guard every
// XOR job would render a confident "0.0%" — a wrong number, which is worse than
// no number.

import { describe, expect, it } from 'vitest'

import { ApiError } from './api'
import { ACTIVE, formatResult, message, summarise } from './train'
import type { Job, ModelSpec, ResultField } from './train'

const percent: ResultField = { key: 'test_accuracy', label: 'test acc', format: 'percent' }
const numeric: ResultField = { key: 'final_loss', label: 'loss', format: 'number' }
const text: ResultField = { key: 'topology', label: 'topology', format: 'text' }

describe('formatResult', () => {
  it('renders a percent field scaled and to one decimal place', () => {
    expect(formatResult(percent, { test_accuracy: 0.923 })).toBe('test acc 92.3%')
  })

  it('renders a numeric field to four decimal places', () => {
    expect(formatResult(numeric, { final_loss: 0.01213 })).toBe('loss 0.0121')
  })

  it('renders a text field verbatim', () => {
    expect(formatResult(text, { topology: '2-8-2' })).toBe('topology 2-8-2')
  })

  // The load-bearing case.
  it('renders nothing rather than 0.0% when the driver reported null', () => {
    expect(formatResult(percent, { test_accuracy: null })).toBe('')
  })

  it.each([
    ['undefined', undefined],
    ['a missing key', Symbol('absent')],
    ['NaN', NaN],
    ['Infinity', Infinity],
    ['-Infinity', -Infinity],
    ['a string', '0.92'],
    ['a boolean', true],
    ['an object', {}],
  ])('renders nothing for %s', (_label, value) => {
    const result = value === undefined ? {} : { test_accuracy: value }
    expect(formatResult(percent, result as Record<string, unknown>)).toBe('')
  })

  it('renders a genuine zero, which is a real measurement', () => {
    // Distinct from the null case above: 0% accuracy happened, null did not.
    expect(formatResult(percent, { test_accuracy: 0 })).toBe('test acc 0.0%')
    expect(formatResult(numeric, { final_loss: 0 })).toBe('loss 0.0000')
  })

  it('renders nothing for an empty or non-string text field', () => {
    expect(formatResult(text, { topology: '' })).toBe('')
    expect(formatResult(text, { topology: null })).toBe('')
    expect(formatResult(text, { topology: 5 })).toBe('')
  })

  it('rounds rather than truncating', () => {
    expect(formatResult(percent, { test_accuracy: 0.9999 })).toBe('test acc 100.0%')
    expect(formatResult(numeric, { final_loss: 0.00005 })).toBe('loss 0.0001')
  })
})

describe('summarise', () => {
  const spec = { result_fields: [percent, numeric] } as ModelSpec
  const job = (result: Record<string, unknown> | null) => ({ result }) as Job

  it('joins every field the run produced', () => {
    expect(summarise(job({ test_accuracy: 1, final_loss: 0.5 }), spec)).toBe(
      'test acc 100.0%, loss 0.5000',
    )
  })

  it('drops the fields the run did not produce', () => {
    // The comma must not survive the field it belonged to.
    expect(summarise(job({ test_accuracy: null, final_loss: 0.5 }), spec)).toBe('loss 0.5000')
  })

  it('returns nothing when the job has no result yet', () => {
    expect(summarise(job(null), spec)).toBe('')
  })

  it('returns nothing when the model spec has not loaded', () => {
    expect(summarise(job({ test_accuracy: 1 }), undefined)).toBe('')
  })

  it('returns nothing when no field matched', () => {
    expect(summarise(job({ unrelated: 1 }), spec)).toBe('')
  })
})

describe('message', () => {
  it('passes an ordinary error through unchanged', () => {
    expect(message(new Error('Login failed'), 'fallback')).toBe('Login failed')
  })

  it('falls back when the thrown value is not an Error', () => {
    expect(message('a bare string', 'Login failed')).toBe('Login failed')
    expect(message(undefined, 'Login failed')).toBe('Login failed')
    expect(message({ message: 'looks like one' }, 'Login failed')).toBe('Login failed')
  })

  it('appends a wait to a rate-limit error, which otherwise reads as a dead end', () => {
    const err = new ApiError(429, 'Too many requests.', 30)
    expect(message(err, 'fallback')).toBe('Too many requests. Try again in 30 seconds.')
  })

  it.each([
    [1, '1 second'],
    [2, '2 seconds'],
    [59, '59 seconds'],
    [60, '1 minute'],
    [61, '2 minutes'],
    [120, '2 minutes'],
    [121, '3 minutes'],
    [3600, '60 minutes'],
  ])('renders retryAfter=%i as "%s"', (seconds, expected) => {
    // Boundaries at the singular/plural switch and at the seconds/minutes switch.
    // Note 61s rounds UP to 2 minutes: a countdown must never finish early.
    const err = new ApiError(429, 'Slow down.', seconds)
    expect(message(err, 'fallback')).toBe(`Slow down. Try again in ${expected}.`)
  })

  it('adds no wait when retryAfter is zero or absent', () => {
    expect(message(new ApiError(429, 'Slow down.', 0), 'fallback')).toBe('Slow down.')
    expect(message(new ApiError(429, 'Slow down.'), 'fallback')).toBe('Slow down.')
  })

  it('adds no wait to a non-rate-limit ApiError', () => {
    expect(message(new ApiError(400, 'Invalid email or password'), 'fallback')).toBe(
      'Invalid email or password',
    )
  })

  it('rounds a fractional wait up', () => {
    expect(message(new ApiError(429, 'Slow down.', 1.2), 'fallback')).toBe(
      'Slow down. Try again in 2 seconds.',
    )
  })
})

describe('ACTIVE', () => {
  it('holds exactly the two non-terminal statuses the backend uses', () => {
    // Must stay in step with ACTIVE_STATUSES in backend/routers/train.py; a
    // mismatch would make the UI stop polling a job that is still running.
    expect([...ACTIVE].sort()).toEqual(['queued', 'running'])
  })

  it('does not treat terminal statuses as active', () => {
    expect(ACTIVE.has('succeeded')).toBe(false)
    expect(ACTIVE.has('failed')).toBe(false)
  })
})
