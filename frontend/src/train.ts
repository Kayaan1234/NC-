// Shared shapes for the training feature, used by both the model menu
// (pages/Training.tsx) and the per-model config page (pages/TrainingModel.tsx).
// Mirrors the backend ModelSpecResponse / JobStatusResponse (see routers/train.py).

export type ModelParams = {
  datasets: string[]
  lr_min: number
  lr_max: number
  lr_default: number
  epochs_max: number
  epochs_default: number
}

export type ModelSpec = {
  model_id: string
  name: string
  description: string
  params: ModelParams
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

export function message(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}
