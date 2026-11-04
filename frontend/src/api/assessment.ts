const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
let csrfToken = ''
export function evidenceFileUrl(path: string) { return `${API_BASE}${path}` }

export type User = { id: string; name: string; email: string; role: 'client' | 'freelancer'; email_verified: boolean }
export type Project = {
  id: string; title: string; description: string | null; currency: string; status: string
  membership_status: 'invited' | 'accepted' | 'declined'; client_name: string; freelancer_name: string
  milestone_count?: number; submitted_count?: number; revision_count?: number
  decision_due_count?: number; active_payment_count?: number; milestones?: Milestone[]
}
export type Milestone = {
  id: string; project_id: string; title: string; acceptance_criteria: string[]; amount: string
  currency: string; due_at: string | null; status: string; evidence_revision: number
  evidence_history?: Evidence[]; assessment_history?: Report[]; decisions?: Decision[]
  payment?: Payment | null
}
export type Evidence = {
  id: string; evidence_revision: number; description: string; evidence_links: string[]
  file_name: string | null; file_url?: string | null; submitted_at: string
}
export type Report = {
  id: string; evidence_revision: number; outcome: string; all_met: boolean; is_stale: boolean
  result_json: AssessmentResponse; created_at: string
}
export type Decision = { decision: string; evidence_revision: number; note: string; created_at: string }
export type Payment = {
  amount: string; refunded_amount?: string; currency: string; status: string; paypal_order_id?: string | null
  paypal_authorization_id?: string | null; paypal_capture_id?: string | null; paypal_approval_url?: string | null
}
export type WorkspaceActivity = {
  event_type: string; actor_type: string; details: Record<string, unknown>; created_at: string
  project_id: string; project_title: string; milestone_id: string | null; milestone_title: string | null
}
export type WorkspacePayment = {
  id: string; milestone_id: string; project_id: string; project_title: string; milestone_title: string
  amount: string; refunded_amount?: string; currency: string; status: string; updated_at: string
}
export type RefundProposal = {
  id: string; payment_id: string; milestone_id: string; project_id: string
  project_title: string; milestone_title: string; amount: string; currency: string
  reason: string; agent_name: string; status: 'pending' | 'processing' | 'refunded' | 'rejected' | 'failed'
  zendesk_ticket_id: string | null; slack_channel_id: string | null; slack_thread_ts: string | null
  paypal_refund_id: string | null; proposed_at: string; reviewed_at: string | null
  refunded_amount?: string
}
export type AssessmentResponse = {
  assessment: {
    milestone_id: string; evidence_revision: number; verdicts: CriterionVerdict[]; all_supported: boolean
    blockers: string[]; overall_summary: string; limitations: string[]
  } | null
  trace: { model: string; prompt_version: string; attempts: number; duration_ms: number; outcome: string; error: string | null }
  report?: { report_id: string; report_version: string; evidence_revision: number; stale: boolean; limitations: string[] }
}
export type CriterionVerdict = {
  criterion_id: number; verdict: 'met' | 'partially_met' | 'not_met' | 'unable_to_verify' | 'supported' | 'not_supported' | 'unclear'
  quote: string | null; reasoning: string; requested_revision: string | null; missing_or_contradictory: string[]
  recommended_next_action: string | null; observed_facts: string[]; model_inferences: string[]
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (!['GET', 'HEAD'].includes((init.method || 'GET').toUpperCase()) && csrfToken) headers.set('X-CSRF-Token', csrfToken)
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'include' })
  const body = response.status === 204 ? null : await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = body?.detail
    throw new Error(typeof detail === 'string' ? detail : body?.message || body?.error || `Request failed (${response.status})`)
  }
  if (body && typeof body.csrf_token === 'string') csrfToken = body.csrf_token
  return body as T
}

export async function currentUser() { return request<{ user: User; csrf_token: string }>('/auth/me') }
export type SignupResult =
  | { verification_required: true; email: string; email_sent: boolean; message: string }
  | { verification_required: false; user: User; csrf_token: string; email_confirmation_enabled: false }
export async function signup(payload: { name: string; email: string; password: string; role: User['role'] }) {
  return request<SignupResult>('/auth/signup', { method: 'POST', body: JSON.stringify(payload) })
}
export async function verifyEmail(token: string) { return request<{ verified: boolean }>('/auth/verify-email', { method: 'POST', body: JSON.stringify({ token }) }) }
export async function resendVerification(email: string) { return request<{ message: string }>('/auth/resend-verification', { method: 'POST', body: JSON.stringify({ email }) }) }
export async function requestPasswordReset(email: string) {
  return request<{ message: string }>('/auth/password-reset/request', { method: 'POST', body: JSON.stringify({ email }) })
}
export async function resetPassword(token: string, password: string) {
  return request<{ success: boolean }>('/auth/password-reset/confirm', { method: 'POST', body: JSON.stringify({ token, password }) })
}
export async function login(payload: { email: string; password: string }) {
  return request<{ user: User; csrf_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify(payload) })
}
export async function logout() { return request<{ success: boolean }>('/auth/logout', { method: 'POST', body: '{}' }) }
export async function getProjects() { return request<Project[]>('/projects') }
export async function createProject(payload: { title: string; description: string; currency: string; freelancer_email: string }) {
  return request<Project>('/projects', { method: 'POST', body: JSON.stringify(payload) })
}
export async function getProject(id: string) { return request<Project>(`/projects/${id}`) }
export async function acceptProject(id: string) { return request(`/projects/${id}/accept`, { method: 'POST', body: '{}' }) }
export async function createMilestone(projectId: string, payload: { title: string; acceptance_criteria: string[]; amount: string; currency: string; due_at?: string }) {
  return request<Milestone>(`/projects/${projectId}/milestones`, { method: 'POST', body: JSON.stringify(payload) })
}
export async function updateMilestone(projectId: string, milestoneId: string, payload: { title: string; acceptance_criteria: string[]; amount: string; currency: string; due_at?: string }) {
  return request<Milestone>(`/projects/${projectId}/milestones/${milestoneId}`, { method: 'PUT', body: JSON.stringify(payload) })
}
export async function updateAccount(payload: { name: string; current_password: string; new_password?: string }) {
  return request<{ user: User; csrf_token: string }>('/auth/me', { method: 'PATCH', body: JSON.stringify(payload) })
}
export async function getMilestone(id: string) { return request<Milestone>(`/milestones/${id}`) }
export async function submitEvidence(id: string, description: string, links: string[], file?: File) {
  let fileBase64: string | undefined
  if (file) {
    if (file.size > 3 * 1024 * 1024) throw new Error('Files must be 3 MB or smaller so they can be uploaded reliably.')
    const bytes = new Uint8Array(await file.arrayBuffer())
    let binary = ''
    for (let index = 0; index < bytes.length; index += 0x8000) {
      binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000))
    }
    fileBase64 = btoa(binary)
  }
  return request<Evidence>(`/milestones/${id}/evidence`, { method: 'POST', body: JSON.stringify({ description, links, file_name: file?.name, file_content_type: file?.type, file_base64: fileBase64 }) })
}
export async function assessMilestone(id: string) { return request<{ result: AssessmentResponse; report_id: string; stale: boolean }>(`/milestones/${id}/assessments`, { method: 'POST', body: '{}' }) }
export async function decideMilestone(id: string, decision: string, note: string) {
  return request(`/milestones/${id}/decision`, { method: 'POST', body: JSON.stringify({ decision, note }) })
}
export async function getAudit(projectId: string) { return request<{ event_type: string; actor_type: string; details: Record<string, unknown>; created_at: string }[]>(`/projects/${projectId}/audit`) }
export async function getWorkspaceActivity() { return request<WorkspaceActivity[]>('/activity') }
export async function getPayments() { return request<WorkspacePayment[]>('/payments') }
export async function getRefundProposals(status = 'all') {
  return request<RefundProposal[]>(`/refund-proposals?status=${encodeURIComponent(status)}`)
}
export async function decideRefundProposal(id: string, decision: 'approve' | 'reject', note = '') {
  return request<{ id: string; status: RefundProposal['status']; paypal_refund_id?: string; message?: string }>(
    `/refund-proposals/${id}/decision`, { method: 'POST', body: JSON.stringify({ decision, note }) },
  )
}
export async function createPaymentOrder(id: string) { return request<{ payment_id: string; order_id: string; approval_url: string; status: string }>(`/milestones/${id}/payment/order`, { method: 'POST', body: '{}' }) }
export async function authorizePayment(id: string) { return request<{ status: string; authorization_id: string }>(`/milestones/${id}/payment/authorize`, { method: 'POST', body: '{}' }) }
export async function capturePayment(id: string) { return request<{ status: string; capture_id?: string; message?: string }>(`/milestones/${id}/payment/capture`, { method: 'POST', body: '{}' }) }
export async function reconcilePayment(id: string) { return request<{ status: string; capture_id?: string; message?: string }>(`/milestones/${id}/payment/reconcile`, { method: 'POST', body: '{}' }) }
