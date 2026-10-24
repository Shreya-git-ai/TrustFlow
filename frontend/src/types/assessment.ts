export type Verdict = 'supported' | 'not_supported' | 'unclear'

export type Criterion = {
  id: number
  text: string
}

export type CriterionVerdict = {
  criterion_id: number
  verdict: Verdict
  quote: string | null
  reasoning: string
  requested_revision: string | null
}

export type AssessmentResponse = {
  assessment: {
    milestone_id: string
    evidence_revision: number
    verdicts: CriterionVerdict[]
    all_supported: boolean
    blockers: string[]
  } | null
  trace: {
    model: string
    prompt_version: string
    attempts: number
    duration_ms: number
    outcome: string
    error: string | null
  }
}

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
    throw new Error(typeof detail === 'string' ? detail : detail?.message || body.error || 'Assessment request failed.')
  }
  return body as AssessmentResponse
}
