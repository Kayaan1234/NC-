// Shared shapes for the training feature, used by both the model menu
// (pages/Training.tsx) and the per-model config page (pages/TrainingModel.tsx).
// Mirrors the backend ModelSpecResponse / JobStatusResponse (see routers/train.py).
//
// Nothing here names a specific model. A model describes its own parameters and
// its own result keys, and both pages render whatever the server sends — so
// adding a rung needs no change in this directory.

import { ApiError } from './api'

export type ParamKind = 'choice' | 'float' | 'int' | 'int_list'

export type ParamSpec = {
  name: string
  kind: ParamKind
  label: string
  default: unknown
  choices: string[]
  minimum: number | null
  maximum: number | null
  max_items: number | null
  item_min: number | null
  item_max: number | null
  help: string
}

export type ResultField = {
  key: string
  label: string
  format: 'percent' | 'number' | 'text'
}

export type ModelSpec = {
  model_id: string
  name: string
  description: string
  params: ParamSpec[]
  result_fields: ResultField[]
  // { dataset: { param_name: value } } — what the form snaps the other fields to
  // when the dataset selection changes.
  dataset_defaults: Record<string, Record<string, unknown>>
}

export type Job = {
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
export const ACTIVE = new Set(['queued', 'running'])

// The single place an exception becomes text a user reads. Every page routes its
// catch blocks through here.
//
// The retry_after branch is the one case where the server's own message isn't
// enough: a rate limit says "too many requests" without saying when to come back,
// which reads as a dead end rather than a wait. api.ts already parses the value
// off the response — until now nothing read it.
export function message(err: unknown, fallback: string): string {
  if (!(err instanceof Error)) return fallback
  if (err instanceof ApiError && err.retryAfter && err.retryAfter > 0) {
    const secs = Math.ceil(err.retryAfter)
    const wait =
      secs >= 60
        ? `${Math.ceil(secs / 60)} minute${Math.ceil(secs / 60) === 1 ? '' : 's'}`
        : `${secs} second${secs === 1 ? '' : 's'}`
    return `${err.message} Try again in ${wait}.`
  }
  return err.message
}

// One "test acc 92.3%" fragment, or '' if the run didn't produce that key.
//
// The typeof guard is load-bearing, NOT defensive tidiness: the drivers print
// explicit nulls — XOR has no test split so `"test_accuracy":null`, and a
// diverged run nulls its loss and accuracy. `null * 100` is 0 in JS, so without
// this a percent field would render a confident "0.0%" on every XOR job. A
// missing number must show as nothing, never as a wrong number.
export function formatResult(field: ResultField, result: Record<string, unknown>): string {
  const value = result[field.key]
  if (field.format === 'text') {
    return typeof value === 'string' && value ? `${field.label} ${value}` : ''
  }
  if (typeof value !== 'number' || !Number.isFinite(value)) return ''
  return field.format === 'percent'
    ? `${field.label} ${(value * 100).toFixed(1)}%`
    : `${field.label} ${value.toFixed(4)}`
}

// The whole summary line for a finished job, driven by its model's spec.
export function summarise(job: Job, spec: ModelSpec | undefined): string {
  if (!spec || !job.result) return ''
  return spec.result_fields
    .flatMap((f) => formatResult(f, job.result as Record<string, unknown>) || [])
    .join(', ')
}
