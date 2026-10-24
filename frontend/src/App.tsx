import { useEffect, useState, type FormEvent } from 'react'
import { assessEvidence, checkApi } from './api/assessment'
import type { AssessmentResponse, Criterion } from './types/assessment'
import './App.css'

type ApiState = 'checking' | 'online' | 'offline'

function App() {
  const [apiState, setApiState] = useState<ApiState>('checking')
  const [milestoneId, setMilestoneId] = useState('demo-milestone-001')
  const [revision, setRevision] = useState('1')
  const [criteria, setCriteria] = useState<Criterion[]>([{ id: 1, text: '' }])
  const [evidence, setEvidence] = useState('')
  const [links, setLinks] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<AssessmentResponse | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    checkApi(controller.signal).then(() => setApiState('online')).catch(() => setApiState('offline'))
    return () => controller.abort()
  }, [])

  function changeCriterion(id: number, text: string) {
    setCriteria((items) => items.map((item) => item.id === id ? { ...item, text } : item))
  }

  function removeCriterion(id: number) {
    setCriteria((items) => items.filter((item) => item.id !== id))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const response = await assessEvidence({
        milestone_id: milestoneId.trim(),
        evidence_revision: Number(revision),
        criteria: criteria.map((item) => ({ ...item, text: item.text.trim() })),
        evidence_text: evidence.trim(),
        evidence_links: links.split('\n').map((link) => link.trim()).filter(Boolean),
      })
      setResult(response)
      setApiState('online')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not reach the assessment service.')
      if (requestError instanceof TypeError) setApiState('offline')
    } finally {
      setLoading(false)
    }
  }

  function addCriterion() {
    setCriteria((items) => [...items, { id: Math.max(0, ...items.map((item) => item.id)) + 1, text: '' }])
  }

  const connectionLabel = apiState === 'checking' ? 'Connecting' : apiState === 'online' ? 'API connected' : 'API offline'

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#top" aria-label="TrustFlow home"><span className="brand-mark" aria-hidden="true"><span /></span>trustflow<span className="brand-period">.</span></a>
      <div className="workspace-switcher"><div className="workspace-avatar">T</div><div className="workspace-copy"><span>Workspace</span><strong>TrustFlow Studio</strong></div><span className="chevron" aria-hidden="true">⌄</span></div>
      <span className="nav-label">WORKSPACE</span>
      <nav className="side-nav" aria-label="Main navigation"><a className="nav-item" href="#overview"><span className="nav-icon">◫</span>Overview</a><a className="nav-item active" href="#review" aria-current="page"><span className="nav-icon">◇</span>Evidence review</a></nav>
      <div className="sidebar-bottom"><div className="sidebar-note"><span className="note-spark">✦</span><strong>Clear work. Fair release.</strong><p>Evidence first, every milestone.</p></div><div className="profile-row"><div className="profile-avatar">TF</div><div className="profile-copy"><strong>Local demo</strong><span>No account connected</span></div></div></div>
    </aside>

    <main className="main-content" id="top">
      <header className="topbar"><div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>Evidence review</strong></div><div className="topbar-actions"><span className={`connection-pill ${apiState}`}><i />{connectionLabel}</span><a className="help-button" href="https://github.com/Shreya-git-ai/TrustFlow" target="_blank" rel="noreferrer" aria-label="TrustFlow repository">?</a></div></header>
      <div className="page-wrap" id="overview">
        <section className="welcome-row"><div><div className="eyebrow"><span className="eyebrow-line" />MILESTONE WORKSPACE</div><h1>Good work deserves <span>clear proof.</span></h1><p className="welcome-copy">Review submitted evidence against the agreed acceptance criteria.</p></div><div className="review-count"><span className="count-icon">✳</span><span><strong>Evidence-led</strong><small>Every verdict includes reasoning</small></span></div></section>
        <section className="summary-grid" aria-label="Review principles"><article className="summary-card"><span className="summary-icon lavender">◎</span><div><span>ASSESSMENT</span><strong>Criterion by criterion</strong></div><span className="summary-tail">01</span></article><article className="summary-card"><span className="summary-icon mint">⌕</span><div><span>VERIFICATION</span><strong>Quotes checked in evidence</strong></div><span className="summary-tail">02</span></article><article className="summary-card"><span className="summary-icon peach">↗</span><div><span>PAYMENT</span><strong>Approval stays with you</strong></div><span className="summary-tail">03</span></article></section>

        <section className="review-layout" id="review">
          <div className="form-panel panel">
            <div className="panel-heading"><div><span className="section-kicker">NEW REVIEW</span><h2>Submit milestone evidence</h2><p>Give the assessor the criteria and evidence needed to make a grounded decision.</p></div><span className="step-badge">EVIDENCE INPUT</span></div>
            <form onSubmit={handleSubmit}>
              <div className="field-row"><label className="field"><span>Milestone ID</span><input value={milestoneId} onChange={(event) => setMilestoneId(event.target.value)} required placeholder="e.g. milestone UUID" /></label><label className="field field-small"><span>Evidence revision</span><input type="number" min="1" step="1" value={revision} onChange={(event) => setRevision(event.target.value)} required /></label></div>
              <div className="criteria-heading"><label>Acceptance criteria <span className="required-dot">*</span></label><span>What was agreed?</span></div>
              <div className="criteria-list">{criteria.map((criterion, index) => <div className="criterion-row" key={criterion.id}><span className="criterion-number">{String(index + 1).padStart(2, '0')}</span><input aria-label={`Acceptance criterion ${index + 1}`} value={criterion.text} onChange={(event) => changeCriterion(criterion.id, event.target.value)} required placeholder="e.g. Checkout displays an order summary" />{criteria.length > 1 && <button type="button" className="remove-criterion" aria-label={`Remove criterion ${index + 1}`} onClick={() => removeCriterion(criterion.id)}>×</button>}</div>)}</div>
              <button type="button" className="add-criterion" onClick={addCriterion}><span>＋</span> Add a criterion</button>
              <label className="field evidence-field"><span>Evidence provided <span className="required-dot">*</span></span><small>Paste the submission details, notes, or relevant excerpts.</small><textarea value={evidence} onChange={(event) => setEvidence(event.target.value)} required maxLength={20_000} rows={6} placeholder="Describe what was delivered and include the evidence you want assessed…" /><span className="character-count">{evidence.length.toLocaleString()} / 20,000</span></label>
              <label className="field links-field"><span>Evidence links <em>OPTIONAL</em></span><small>One URL per line. Links are recorded in the prompt, but are not opened.</small><textarea value={links} onChange={(event) => setLinks(event.target.value)} rows={2} placeholder="https://…" /></label>
              {error && <div className="error-message" role="alert"><span>!</span>{error}</div>}
              <div className="form-footer"><span><span className="lock-icon">◈</span> Assessment does not approve payment</span><button className="submit-button" type="submit" disabled={loading}>{loading ? <><span className="spinner" />Assessing…</> : <>Run assessment <span>→</span></>}</button></div>
            </form>
          </div>
          <aside className="result-column" aria-live="polite">{result ? <AssessmentResultView result={result} /> : <div className="result-empty panel"><div className="empty-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="art-center"><span>✦</span></div><span className="art-star star-one">✳</span><span className="art-star star-two">✦</span><span className="art-dot dot-one"/><span className="art-dot dot-two"/></div><span className="section-kicker">YOUR REVIEW</span><h2>Clarity starts with evidence.</h2><p>After submission, each criterion and supporting evidence will appear here.</p><div className="empty-checklist"><span><i>✓</i> Exact evidence quotes</span><span><i>✓</i> Clear revision requests</span><span><i>✓</i> You control approval</span></div></div>}
            <div className="tip-card"><span className="tip-icon">✦</span><div><strong>Make evidence easy to verify</strong><p>Use specific details, dates, and outcomes. The assessor can only evaluate information included here.</p></div></div>
          </aside>
        </section>
        <footer className="page-footer"><span>TRUSTFLOW <b>·</b> FAIR MILESTONES, BUILT ON PROOF</span><span>Assessment assistance by Gemini AI</span></footer>
      </div>
    </main>
  </div>
}

function AssessmentResultView({ result }: { result: AssessmentResponse }) {
  const assessment = result.assessment
  const passed = assessment?.all_supported ?? false
  const label = result.trace.outcome === 'ok' ? passed ? 'All criteria supported' : 'Review needs attention' : result.trace.outcome.replaceAll('_', ' ')
  return <div className="result-card panel"><div className="result-head"><div><span className="section-kicker">ASSESSMENT RESULT</span><h2>Review summary</h2></div><span className={`result-status ${passed ? 'passed' : 'needs-review'}`}><i />{label}</span></div>
    {assessment ? <><div className="result-meta"><span>Milestone <strong>{assessment.milestone_id}</strong></span><span>Revision <strong>#{assessment.evidence_revision}</strong></span></div><div className="verdict-list">{assessment.verdicts.map((item) => <article className="verdict-item" key={item.criterion_id}><div className="verdict-top"><span className="verdict-id">Criterion {String(item.criterion_id).padStart(2, '0')}</span><span className={`verdict-badge ${item.verdict}`}>{item.verdict.replaceAll('_', ' ')}</span></div>{item.quote && <blockquote>“{item.quote}”</blockquote>}<p>{item.reasoning}</p>{item.requested_revision && <div className="revision-request"><span>↗</span><span><small>REQUESTED REVISION</small>{item.requested_revision}</span></div>}</article>)}</div>{assessment.blockers.length > 0 && <p className="blocker-note">{assessment.blockers.length} item{assessment.blockers.length === 1 ? '' : 's'} need follow-up before you decide.</p>}</> : <div className="result-error"><span>!</span><div><strong>Assessment could not be completed</strong><p>{result.trace.error || 'Try again after checking the backend and model configuration.'}</p></div></div>}
    <div className="trace-footer"><span><i />{result.trace.model}</span><span>{(result.trace.duration_ms / 1000).toFixed(1)}s</span><span>{result.trace.attempts} attempt{result.trace.attempts === 1 ? '' : 's'}</span></div>
  </div>
}

export default App
