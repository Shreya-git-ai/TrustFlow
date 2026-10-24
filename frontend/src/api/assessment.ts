import type { AssessmentResponse, Criterion } from '../types/assessment'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export async function checkApi(signal: AbortSignal): Promise<void> {
  const response = await fetch(`${API_BASE}/health`, { signal })
  if (!response.ok) throw new Error('Backend unavailable')
}

export async function assessEvidence(payload: {
  milestone_id: string
  evidence_revision: number
  criteria: Criterion[]
  evidence_text: string
  evidence_links: string[]
}): Promise<AssessmentResponse> {
  const response = await fetch(`${API_BASE}/assessments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(65_000),
  })
  const body = await response.json()
  if (!response.ok) {
    const detail = body.detail
    const message = typeof detail === 'string'
      ? detail
      : detail?.trace?.error
        ? `${detail.message}: ${detail.trace.error}`
        : detail?.message || body.error
    throw new Error(message || 'Assessment request failed.')
  }
  return body as AssessmentResponse
}
