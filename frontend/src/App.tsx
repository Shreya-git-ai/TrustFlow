import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  acceptProject, assessMilestone, authorizePayment, capturePayment, createMilestone, evidenceFileUrl,
  createPaymentOrder, createProject, currentUser, decideMilestone, getAudit, getMilestone,
  getProject, getProjects, login, logout, reconcilePayment, resendVerification, signup, submitEvidence,
  updateAccount, updateMilestone, verifyEmail,
  type AssessmentResponse, type Milestone, type Project, type User,
} from './api/assessment'
import './App.css'

type AuthMode = 'login' | 'signup'

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [projects, setProjects] = useState<Project[]>([])
  const [project, setProject] = useState<Project | null>(null)
  const [milestone, setMilestone] = useState<Milestone | null>(null)
  const [audit, setAudit] = useState<Awaited<ReturnType<typeof getAudit>>>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(() => {
    if (window.location.pathname === '/payment-return') return 'PayPal returned you to TrustFlow. Confirm buyer approval to authorize the milestone payment.'
    if (window.location.pathname === '/payment-cancel') return 'PayPal checkout was cancelled. The payment remains unchanged.'
    return ''
  })
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [pendingVerificationEmail, setPendingVerificationEmail] = useState('')
  const [pendingVerificationMessage, setPendingVerificationMessage] = useState('')
  const [verificationStatus, setVerificationStatus] = useState<'checking' | 'verified' | 'error' | null>(() => {
    if (window.location.pathname !== '/verify-email') return null
    return window.location.hash.length > 1 ? 'checking' : 'error'
  })

  const loadProjects = useCallback(async () => setProjects(await getProjects()), [])
  useEffect(() => {
    currentUser().then(async (response) => {
      setUser(response.user)
      setProjects(await getProjects())
    }).catch((e: unknown) => {
      setUser(null)
      if (e instanceof Error && e.message !== 'Authentication required') setError(e.message)
    })
  }, [])

  useEffect(() => {
    if (window.location.pathname !== '/verify-email') return
    let active = true
    const token = window.location.hash.slice(1)
    if (!token) {
      return () => { active = false }
    }
    verifyEmail(token).then(() => {
      if (active) setVerificationStatus('verified')
    }).catch(() => {
      if (active) setVerificationStatus('error')
    })
    return () => { active = false }
  }, [])

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('')
    try { await action() } catch (e) { setError(e instanceof Error ? e.message : 'The request failed.') }
    finally { setBusy(false) }
  }

  async function openProject(id: string) {
    await run(async () => {
      const selected = await getProject(id)
      setSettingsOpen(false)
      setProject(selected); setMilestone(null); setAudit(await getAudit(id))
    })
  }

  async function refreshSelected() {
    if (!project) return
    const selected = await getProject(project.id)
    setProject(selected)
    setProjects(await getProjects())
    if (milestone) setMilestone(await getMilestone(milestone.id))
    setAudit(await getAudit(project.id))
  }

  async function selectMilestone(id: string) {
    await run(async () => setMilestone(await getMilestone(id)))
  }

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    await run(async () => {
      if (authMode === 'signup') {
        const response = await signup({ name: String(values.get('name') || ''), email: String(values.get('email')), password: String(values.get('password')), role: String(values.get('role')) as User['role'] })
        if (response.verification_required) {
          setPendingVerificationEmail(response.email)
          setPendingVerificationMessage(response.message)
          return
        }
        setUser(response.user)
        setProjects(await getProjects())
        setNotice('Email confirmation is off in local development. Configure SMTP to test the confirmation flow.')
      } else {
        const response = await login({ email: String(values.get('email')), password: String(values.get('password')) })
        setUser(response.user)
        setProjects(await getProjects())
      }
    })
  }

  async function resendConfirmation(email: string): Promise<string> {
    setBusy(true); setError('')
    try {
      const response = await resendVerification(email)
      setPendingVerificationMessage(response.message)
      return response.message
    } catch (e) {
      const message = e instanceof Error ? e.message : 'The request failed.'
      setError(message)
      return ''
    } finally {
      setBusy(false)
    }
  }

  async function signOut() {
    await run(async () => { await logout(); setUser(null); setProject(null); setMilestone(null); setProjects([]); setSettingsOpen(false) })
  }

  if (window.location.pathname === '/verify-email') return <EmailVerificationPage status={verificationStatus || 'checking'} onResend={resendConfirmation} busy={busy} error={error} />
  if (pendingVerificationEmail) return <VerificationPending email={pendingVerificationEmail} message={pendingVerificationMessage} busy={busy} error={error} onResend={resendConfirmation} onBack={() => { setPendingVerificationEmail(''); setAuthMode('login'); setError('') }} />
  if (!['/', '/payment-return', '/payment-cancel'].includes(window.location.pathname)) return <main className="not-found-page"><section className="surface"><span className="eyebrow">404 · PAGE NOT FOUND</span><h1>We couldn’t find that page.</h1><p>Use your workspace navigation to return to a project.</p><a className="primary-button link-button" href="/">Go to TrustFlow</a></section></main>
  if (!user) return <AuthScreen mode={authMode} setMode={setAuthMode} onSubmit={handleAuth} busy={busy} error={error} />

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#home"><span className="brand-mark">T</span>trustflow<span className="brand-dot">.</span></a>
      <div className="workspace-chip"><span className="workspace-avatar">{user.name.slice(0, 1).toUpperCase()}</span><span><small>WORKSPACE</small><strong>{user.role === 'client' ? 'Client studio' : 'Freelancer desk'}</strong></span></div>
      <p className="nav-caption">MENU</p>
      <button className={`nav-link ${!project && !settingsOpen ? 'selected' : ''}`} onClick={() => { setProject(null); setMilestone(null); setSettingsOpen(false) }}><span>▦</span>Overview</button>
      {project && <button className="nav-link selected" onClick={() => { setMilestone(null); void openProject(project.id) }}><span>◇</span>Project details</button>}
      <button className={`nav-link ${settingsOpen ? 'selected' : ''}`} onClick={() => { setProject(null); setMilestone(null); setSettingsOpen(true) }}><span>⚙</span>Account settings</button>
      <div className="sidebar-bottom"><div className="principle-card"><span>✦</span><strong>Evidence first.</strong><p>People decide. AI assists.</p></div><div className="account-mini"><div className="avatar">{user.name.slice(0, 1).toUpperCase()}</div><div><strong>{user.name}</strong><small>{user.role}</small></div><button className="icon-button" onClick={() => void signOut()} aria-label="Log out" title="Log out">↗</button></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div className="crumb">TrustFlow <span>/</span> {project ? project.title : 'Overview'}</div><div className="topbar-user"><span className="online-dot"/>Signed in as {user.role}<button className="text-button" onClick={() => void signOut()}>Log out</button></div></header>
      <div className="content">
        {error && <div role="alert" className="alert error-alert"><strong>Could not complete that action.</strong> {error}<button onClick={() => setError('')} aria-label="Dismiss">×</button></div>}
        {notice && <div role="status" className="alert success-alert">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss">×</button></div>}
        {!project && settingsOpen ? <SettingsPage user={user} busy={busy} onSave={(data) => void run(async () => { const response = await updateAccount(data); setUser(response.user); setNotice('Account settings saved. Your session was rotated.') })} /> : !project ? <Dashboard user={user} projects={projects} busy={busy} onOpen={openProject} onAccept={(id) => void run(async () => { await acceptProject(id); await loadProjects(); setNotice('Project invitation accepted.') })} onCreate={(data) => void run(async () => { await createProject(data); await loadProjects(); setNotice('Project created and invitation sent to the registered freelancer.') })} /> : milestone ? <MilestonePage
          milestone={milestone} project={project} user={user} busy={busy} audit={audit}
          onBack={() => setMilestone(null)} onRefresh={() => void run(refreshSelected)}
          onUpdate={(data) => void run(async () => { await updateMilestone(project.id, milestone.id, data); await refreshSelected(); setNotice('Milestone terms updated.') })}
          onEvidence={(description, links, file) => void run(async () => { await submitEvidence(milestone.id, description, links, file); await refreshSelected(); setNotice('Evidence revision submitted. A client can now request an assessment.') })}
          onAssess={() => void run(async () => { const report = await assessMilestone(milestone.id); await refreshSelected(); setNotice(report.stale ? 'Assessment saved, but the evidence changed while it was running. Review the latest revision.' : 'Assessment report saved to project history.') })}
          onDecision={(decision, note) => void run(async () => { await decideMilestone(milestone.id, decision, note); await refreshSelected(); setNotice(decision === 'approved' ? 'Milestone approved by the client.' : decision === 'revoked' ? 'Approval revoked.' : 'Revision requested.') })}
          onOrder={() => void run(async () => { const payment = await createPaymentOrder(milestone.id); await refreshSelected(); setNotice('PayPal order created. Continue at PayPal, then return here to authorize it.'); if (payment.approval_url) window.open(payment.approval_url, '_blank', 'noopener,noreferrer') })}
          onAuthorize={() => void run(async () => { await authorizePayment(milestone.id); await refreshSelected(); setNotice('PayPal authorization confirmed.') })}
          onCapture={() => void run(async () => { if (!window.confirm('Capture the authorized milestone amount from PayPal?')) return; const result = await capturePayment(milestone.id); await refreshSelected(); setNotice(result.status === 'captured' ? 'PayPal confirmed the capture.' : 'Capture is pending. TrustFlow will not submit another capture until PayPal is reconciled.') })}
          onReconcile={() => void run(async () => { const result = await reconcilePayment(milestone.id); await refreshSelected(); setNotice(result.status === 'captured' ? 'PayPal confirmed the capture.' : 'PayPal still has no completed capture to report.') })}
        /> : <ProjectPage project={project} user={user} busy={busy} onBack={() => { setProject(null); setMilestone(null) }} onSelect={selectMilestone} onCreateMilestone={(data) => void run(async () => { await createMilestone(project.id, data); await refreshSelected(); setNotice('Milestone added to the project.') })} />}
      </div>
    </main>
  </div>
}

function PasswordField({
  label, name, autoComplete, required = false, minLength, maxLength = 128, hint,
}: {
  label: string; name: string; autoComplete: string; required?: boolean
  minLength?: number; maxLength?: number; hint?: string
}) {
  const [visible, setVisible] = useState(false)
  return <label className="password-field">
    <span>{label}</span>
    <span className="password-input-wrap">
      <input name={name} type={visible ? 'text' : 'password'} autoComplete={autoComplete} required={required} minLength={minLength} maxLength={maxLength} />
      <button type="button" className="password-toggle" onClick={() => setVisible((shown) => !shown)} aria-label={visible ? 'Hide password' : 'Show password'} aria-pressed={visible}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.7"/>{visible && <path d="m4 4 16 16"/>}</svg>
        <span>{visible ? 'Hide' : 'Show'}</span>
      </button>
    </span>
    {hint && <small>{hint}</small>}
  </label>
}

function AuthScreen({ mode, setMode, onSubmit, busy, error }: {
  mode: AuthMode; setMode: (value: AuthMode) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void; busy: boolean; error: string
}) {
  return <main className="auth-layout auth-enter">
    <section className="auth-story">
      <a className="brand light-brand" href="#home"><span className="brand-mark">T</span>trustflow<span className="brand-dot">.</span></a>
      <div className="story-content"><span className="eyebrow">FREELANCE WORK, WITH CLARITY</span><h1>Good work should be easy to <em>prove.</em></h1><p>Agree on the milestone. Share evidence. Make the final decision together.</p><div className="story-steps"><span><b>01</b> Agree on criteria</span><span><b>02</b> Review evidence</span><span><b>03</b> Client approves</span></div></div>
      <small className="story-foot">TrustFlow uses AI to assist review. Only the client makes approval decisions.</small>
    </section>
    <section className="auth-panel"><div className="auth-card">
      <div className="auth-heading"><span className="eyebrow">YOUR WORKSPACE</span><h2>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2><p>{mode === 'login' ? 'Sign in to continue to your projects.' : 'Set up an account as a client or freelancer.'}</p></div>
      <form onSubmit={onSubmit} className="stack-form">
        {mode === 'signup' && <><label>Name<input name="name" autoComplete="name" required maxLength={100} /></label><label>Account role<select name="role" defaultValue="client"><option value="client">Client</option><option value="freelancer">Freelancer</option></select></label></>}
        <label>Email<input name="email" type="email" autoComplete="email" required maxLength={254} /></label>
        <PasswordField label="Password" name="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'signup' ? 12 : 1} hint={mode === 'signup' ? 'Use at least 12 characters.' : undefined}/>
        {error && <p className="inline-error" role="alert">{error}</p>}
        <button className="primary-button full-button" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}<span>→</span></button>
      </form>
      <p className="switch-auth">{mode === 'login' ? 'New to TrustFlow?' : 'Already have an account?'} <button onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}>{mode === 'login' ? 'Create account' : 'Sign in'}</button></p>
      <p className="auth-limit">New accounts confirm their email when mail delivery is configured. Password recovery is not available yet.</p>
    </div></section>
  </main>
}

function VerificationPending({ email, message, busy, error, onResend, onBack }: {
  email: string; message: string; busy: boolean; error: string
  onResend: (email: string) => Promise<string>; onBack: () => void
}) {
  return <main className="verification-page auth-enter"><section className="verification-card surface">
    <span className="verification-icon">✉</span><span className="eyebrow">ONE QUICK CHECK</span><h1>Check your inbox</h1>
    <p>{message || 'We sent a confirmation link to your email address.'}</p><strong className="verification-address">{email}</strong>
    <ResendVerificationForm initialEmail={email} busy={busy} error={error} onResend={onResend}/>
    <button className="text-button verification-back" onClick={onBack}>Back to sign in</button>
  </section></main>
}

function EmailVerificationPage({ status, onResend, busy, error }: {
  status: 'checking' | 'verified' | 'error'; onResend: (email: string) => Promise<string>; busy: boolean; error: string
}) {
  return <main className="verification-page auth-enter"><section className="verification-card surface">
    {status === 'checking' ? <><span className="verification-spinner"/><span className="eyebrow">VERIFYING</span><h1>Checking your link</h1><p>This will only take a moment.</p></> : status === 'verified' ? <><span className="verification-icon verified">✓</span><span className="eyebrow">EMAIL CONFIRMED</span><h1>You’re all set</h1><p>Your email is verified. Sign in to open your TrustFlow workspace.</p><a className="primary-button link-button" href="/">Continue to sign in <span>→</span></a></> : <><span className="verification-icon invalid">!</span><span className="eyebrow">LINK UNAVAILABLE</span><h1>That link has expired</h1><p>Confirmation links work once and expire after 24 hours. Request a fresh one below.</p><ResendVerificationForm busy={busy} error={error} onResend={onResend}/><a className="text-button verification-back" href="/">Back to sign in</a></>}
  </section></main>
}

function ResendVerificationForm({ initialEmail = '', busy, error, onResend }: {
  initialEmail?: string; busy: boolean; error: string; onResend: (email: string) => Promise<string>
}) {
  const [message, setMessage] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const email = String(new FormData(event.currentTarget).get('email') || '')
    setMessage(await onResend(email))
  }
  return <form className="resend-form" onSubmit={(event) => void submit(event)}>
    {!initialEmail && <label>Email<input name="email" type="email" autoComplete="email" required maxLength={254}/></label>}
    <button className="secondary-button" disabled={busy}>{busy ? 'Sending…' : 'Resend confirmation email'}</button>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {message && <p className="resend-message" role="status">{message}</p>}
  </form>
}
function Dashboard({ user, projects, busy, onOpen, onAccept, onCreate }: { user: User; projects: Project[]; busy: boolean; onOpen: (id: string) => void; onAccept: (id: string) => void; onCreate: (data: { title: string; description: string; currency: string; freelancer_email: string }) => void }) {
  return <><div className="page-heading"><div><span className="eyebrow">{user.role === 'client' ? 'CLIENT DASHBOARD' : 'FREELANCER DASHBOARD'}</span><h1>{user.role === 'client' ? 'Your projects, clearly.' : 'Your next milestone.'}</h1><p>{user.role === 'client' ? 'Coordinate work, review evidence, and make the approval decision.' : 'See invitations, requirements, submissions, and payment status.'}</p></div><span className="heading-mark">✳</span></div>
    <div className="stat-row"><Stat label="PROJECTS" value={projects.length} icon="▦"/><Stat label="MILESTONES" value={projects.reduce((sum, item) => sum + (item.milestone_count || 0), 0)} icon="◇"/><Stat label={user.role === 'client' ? 'SUBMITTED' : 'REVISION REQUESTS'} value={projects.reduce((sum, item) => sum + (user.role === 'client' ? item.submitted_count || 0 : item.revision_count || 0), 0)} icon="◎"/><Stat label="CLIENT DECISIONS DUE" value={projects.reduce((sum, item) => sum + (item.decision_due_count || 0), 0)} icon="✓"/><Stat label="ACTIVE PAYMENTS" value={projects.reduce((sum, item) => sum + (item.active_payment_count || 0), 0)} icon="$"/></div>
    <div className="dashboard-grid"><section className="surface project-section"><div className="section-head"><div><span className="eyebrow">WORKSPACE</span><h2>Projects</h2></div><span className="subtle-count">{projects.length} total</span></div>{projects.length === 0 ? <div className="empty-state"><span>◇</span><h3>No projects yet</h3><p>{user.role === 'client' ? 'Create a project and invite a registered freelancer.' : 'Your client’s invitation will appear here.'}</p></div> : <div className="project-list">{projects.map((item) => <article className="project-row" key={item.id}><div className="project-symbol">{item.title.slice(0, 1).toUpperCase()}</div><div className="project-row-main"><strong>{item.title}</strong><span>{user.role === 'client' ? `Freelancer: ${item.freelancer_name}` : `Client: ${item.client_name}`}</span></div><div className="project-row-meta"><span className={`status-chip ${item.membership_status}`}>{item.membership_status === 'invited' ? 'Invitation pending' : 'Active'}</span><small>{item.milestone_count || 0} milestones</small></div>{item.membership_status === 'invited' && user.role === 'freelancer' ? <button className="secondary-button" disabled={busy} onClick={() => onAccept(item.id)}>Accept</button> : <button className="arrow-button" aria-label={`Open ${item.title}`} onClick={() => onOpen(item.id)}>→</button>}</article>)}</div>}</section>
      {user.role === 'client' && <CreateProjectForm busy={busy} onCreate={onCreate}/>}<section className="surface guide-card"><span className="guide-icon">✦</span><div><span className="eyebrow">HOW TRUSTFLOW WORKS</span><h3>Evidence informs. People decide.</h3><p>AI reviews only the evidence text provided. It does not approve milestones or move money.</p></div><div className="guide-flow"><span>Criteria</span><i>→</i><span>Evidence</span><i>→</i><span>Client decision</span></div></section></div>
  </>
}

function Stat({ label, value, icon }: { label: string; value: string | number; icon: string }) { return <div className="stat-card"><span className="stat-icon">{icon}</span><div><small>{label}</small><strong>{value}</strong></div></div> }

function SettingsPage({ user, busy, onSave }: { user: User; busy: boolean; onSave: (data: { name: string; current_password: string; new_password?: string }) => void }) {
  const [passwordError, setPasswordError] = useState('')
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const next = String(data.get('new_password') || '')
    if (next && next !== String(data.get('confirm_password') || '')) {
      setPasswordError('The new passwords do not match.')
      return
    }
    setPasswordError('')
    onSave({ name: String(data.get('name')), current_password: String(data.get('current_password')), new_password: next || undefined })
  }
  return <><div className="page-heading"><div><span className="eyebrow">ACCOUNT</span><h1>Account settings</h1><p>Update your profile and password. Your role is fixed after signup.</p></div></div><section className="surface settings-card"><div className="section-head"><div><span className="eyebrow">PROFILE AND SECURITY</span><h2>Your account</h2></div><span className="status-chip accepted">{user.role}</span></div><form className="stack-form" onSubmit={submit}><label>Name<input name="name" defaultValue={user.name} required maxLength={100}/></label><label>Email<input value={user.email} readOnly/><small>{user.email_verified ? 'Email confirmed.' : 'Email confirmation is still pending.'}</small></label><PasswordField label="Current password" name="current_password" autoComplete="current-password" required/><div className="settings-password-row"><PasswordField label="New password" name="new_password" autoComplete="new-password" minLength={12} hint="Leave blank to keep your current password."/><PasswordField label="Confirm new password" name="confirm_password" autoComplete="new-password" minLength={12}/></div>{passwordError && <p className="inline-error" role="alert">{passwordError}</p>}<button className="primary-button" disabled={busy}>Save settings <span>→</span></button></form><div className="settings-note"><strong>Password recovery</strong><p>Recovery email delivery is not configured. Keep your password safe; lost account recovery is an MVP limitation.</p></div></section></>
}
function CreateProjectForm({ busy, onCreate }: { busy: boolean; onCreate: (data: { title: string; description: string; currency: string; freelancer_email: string }) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); onCreate({ title: String(data.get('title')), description: String(data.get('description') || ''), currency: String(data.get('currency')).toUpperCase(), freelancer_email: String(data.get('freelancer_email')) }) ; event.currentTarget.reset() }
  return <section className="surface create-card"><div className="section-head"><div><span className="eyebrow">START A COLLABORATION</span><h2>New project</h2></div><span className="create-plus">＋</span></div><form className="stack-form compact-form" onSubmit={submit}><label>Project name<input name="title" required maxLength={160} placeholder="Website redesign"/></label><label>Freelancer account email<input name="freelancer_email" type="email" required placeholder="name@example.com"/></label><label>Project description<textarea name="description" maxLength={5000} rows={3} placeholder="What are you building together?"/></label><label>Currency<input name="currency" defaultValue="USD" minLength={3} maxLength={3} required/></label><button className="primary-button" disabled={busy}>Create project <span>→</span></button><small className="form-hint">The freelancer must already have a TrustFlow account to receive the invitation.</small></form></section>
}

function ProjectPage({ project, user, busy, onBack, onSelect, onCreateMilestone }: { project: Project; user: User; busy: boolean; onBack: () => void; onSelect: (id: string) => void; onCreateMilestone: (data: { title: string; acceptance_criteria: string[]; amount: string; currency: string; due_at?: string }) => void }) {
  return <><button className="back-button" onClick={onBack}>← All projects</button><div className="page-heading project-title-heading"><div><span className="eyebrow">PROJECT · {project.membership_status.toUpperCase()}</span><h1>{project.title}</h1><p>{project.description || 'Milestones, evidence, and decisions for this collaboration.'}</p></div><div className="project-people"><span className="person-dot">{project.client_name?.slice(0,1)}</span><span>{project.client_name} <small>Client</small></span><span className="person-dot secondary-person">{project.freelancer_name?.slice(0,1)}</span><span>{project.freelancer_name} <small>Freelancer</small></span></div></div>
    <div className="project-layout"><section className="surface"><div className="section-head"><div><span className="eyebrow">AGREED WORK</span><h2>Milestones</h2></div><span className="subtle-count">{project.milestones?.length || 0} total</span></div>{project.membership_status === 'invited' && <div className="notice-box">The freelancer has not accepted the invitation. Milestone evidence is unavailable until they accept.</div>}{!project.milestones?.length ? <div className="empty-state"><span>◇</span><h3>No milestones added</h3><p>The client can define the deliverable, criteria, amount, and due date here.</p></div> : <div className="milestone-list">{project.milestones.map((item) => <button className="milestone-row" key={item.id} onClick={() => onSelect(item.id)}><span className="milestone-number">{item.title.slice(0,1).toUpperCase()}</span><span className="milestone-info"><strong>{item.title}</strong><small>{item.acceptance_criteria.length} criteria · revision {item.evidence_revision}</small></span><span className={`status-chip status-${item.status}`}>{item.status.replaceAll('_', ' ')}</span><span className="milestone-amount">{item.currency} {item.amount}</span><span className="row-arrow">→</span></button>)}</div>}</section>{user.role === 'client' && <CreateMilestoneForm project={project} busy={busy} onCreate={onCreateMilestone}/>}</div>
  </>
}

function CreateMilestoneForm({ project, busy, onCreate }: { project: Project; busy: boolean; onCreate: (data: { title: string; acceptance_criteria: string[]; amount: string; currency: string; due_at?: string }) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); const criteria = String(data.get('criteria')).split('\n').map((item) => item.trim()).filter(Boolean); onCreate({ title: String(data.get('title')), acceptance_criteria: criteria, amount: String(data.get('amount')), currency: String(data.get('currency')).toUpperCase(), due_at: data.get('due_at') ? new Date(String(data.get('due_at'))).toISOString() : undefined }); event.currentTarget.reset() }
  return <section className="surface create-card"><div className="section-head"><div><span className="eyebrow">DEFINE THE AGREEMENT</span><h2>Add milestone</h2></div></div><form className="stack-form compact-form" onSubmit={submit}><label>Milestone name<input name="title" required maxLength={160} placeholder="Design handoff"/></label><label>Acceptance criteria<textarea name="criteria" required rows={5} placeholder={'One criterion per line\nFinal designs include mobile layouts\nSource files are included'} /></label><label>Agreed amount<input name="amount" type="number" step="0.01" min="0.01" required placeholder="500.00"/></label><label>Currency<input name="currency" defaultValue={project.currency} minLength={3} maxLength={3} required/></label><label>Deadline (optional)<input name="due_at" type="datetime-local"/></label><button className="primary-button" disabled={busy}>Add milestone <span>→</span></button></form></section>
}

function localDateTime(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

function EditMilestoneForm({ milestone, busy, onUpdate }: { milestone: Milestone; busy: boolean; onUpdate: (data: { title: string; acceptance_criteria: string[]; amount: string; currency: string; due_at?: string }) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const criteria = String(data.get('criteria')).split('\n').map((item) => item.trim()).filter(Boolean)
    onUpdate({ title: String(data.get('title')), acceptance_criteria: criteria, amount: String(data.get('amount')), currency: String(data.get('currency')).toUpperCase(), due_at: data.get('due_at') ? new Date(String(data.get('due_at'))).toISOString() : undefined })
  }
  return <details className="surface edit-milestone"><summary>Edit agreed terms</summary><p>Terms lock after evidence submission or payment begins.</p><form className="stack-form compact-form" onSubmit={submit}><label>Milestone name<input name="title" defaultValue={milestone.title} required maxLength={160}/></label><label>Acceptance criteria<textarea name="criteria" defaultValue={milestone.acceptance_criteria.join('\n')} rows={5} required/></label><label>Agreed amount<input name="amount" type="number" min="0.01" step="0.01" defaultValue={milestone.amount} required/></label><label>Currency<input name="currency" defaultValue={milestone.currency} minLength={3} maxLength={3} required/></label><label>Deadline<input name="due_at" type="datetime-local" defaultValue={localDateTime(milestone.due_at)}/></label><button className="primary-button" disabled={busy}>Save milestone terms <span>→</span></button></form></details>
}

function MilestonePage({ milestone, project, user, busy, audit, onBack, onRefresh, onUpdate, onEvidence, onAssess, onDecision, onOrder, onAuthorize, onCapture, onReconcile }: {
  milestone: Milestone; project: Project; user: User; busy: boolean; audit: Awaited<ReturnType<typeof getAudit>>
  onBack: () => void; onRefresh: () => void; onUpdate: (data: { title: string; acceptance_criteria: string[]; amount: string; currency: string; due_at?: string }) => void; onEvidence: (text: string, links: string[], file?: File) => void
  onAssess: () => void; onDecision: (decision: string, note: string) => void; onOrder: () => void
  onAuthorize: () => void; onCapture: () => void; onReconcile: () => void
}) {
  const report: AssessmentResponse | undefined = milestone.assessment_history?.[0]?.result_json
  const isClient = user.role === 'client'
  function evidenceSubmit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); const text = String(data.get('description') || ''); const links = String(data.get('links') || '').split('\n').map((value) => value.trim()).filter(Boolean); const file = data.get('file'); onEvidence(text, links, file instanceof File && file.size ? file : undefined); event.currentTarget.reset() }
  const latestReportCurrent = !!report && report.report?.evidence_revision === milestone.evidence_revision && !milestone.assessment_history?.[0]?.is_stale
  const currentReport = !!report?.assessment && latestReportCurrent
  return <><button className="back-button" onClick={onBack}>← {project.title}</button><div className="page-heading milestone-title-heading"><div><span className="eyebrow">MILESTONE · REVISION {milestone.evidence_revision}</span><h1>{milestone.title}</h1><p>{milestone.currency} {milestone.amount}{milestone.due_at ? ` · Due ${new Date(milestone.due_at).toLocaleDateString()}` : ''}</p></div><span className={`status-chip status-${milestone.status}`}>{milestone.status.replaceAll('_', ' ')}</span></div>
    <div className="milestone-work-grid"><div className="work-column"><section className="surface criteria-card"><div className="section-head"><div><span className="eyebrow">THE AGREEMENT</span><h2>Acceptance criteria</h2></div></div><ol className="criteria-list">{milestone.acceptance_criteria.map((item, index) => <li key={`${index}-${item}`}><span>{String(index + 1).padStart(2,'0')}</span>{item}</li>)}</ol></section>{user.role === 'client' && milestone.evidence_revision === 0 && !milestone.payment && <EditMilestoneForm milestone={milestone} busy={busy} onUpdate={onUpdate}/>}
      {user.role === 'freelancer' && <section className="surface"><div className="section-head"><div><span className="eyebrow">SUBMISSION</span><h2>Submit evidence</h2><p>Text, reference links, or a file. Links and files are stored but not opened or extracted by assessment.</p></div></div><form className="stack-form" onSubmit={evidenceSubmit}><label>What did you deliver?<textarea name="description" rows={5} maxLength={20000} placeholder="Add specific details and evidence excerpts…"/><small>Up to 20,000 characters. Any attachment is saved privately; its contents are not analyzed.</small></label><label>Reference links <textarea name="links" rows={2} placeholder="One http(s) URL per line"/></label><label>Attach a file<input name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.txt,.csv,application/pdf,image/png,image/jpeg,text/plain,text/csv"/><small>PDF, PNG, JPEG, TXT, or CSV · 10 MB maximum.</small></label><button className="primary-button" disabled={busy}>Submit evidence revision <span>→</span></button></form></section>}
      <section className="surface"><div className="section-head"><div><span className="eyebrow">EVIDENCE HISTORY</span><h2>Submissions</h2></div><span className="subtle-count">{milestone.evidence_history?.length || 0}</span></div>{!milestone.evidence_history?.length ? <p className="muted">No evidence has been submitted yet.</p> : <div className="history-list">{milestone.evidence_history.map((item) => <article className="history-item" key={item.id}><span className="history-rev">R{item.evidence_revision}</span><div><strong>{new Date(item.submitted_at).toLocaleString()}</strong><p>{item.description || 'No text description submitted.'}</p>{item.file_name && <><small>Attachment saved: {item.file_name} · not inspected</small>{item.file_url && <a className="file-download" href={evidenceFileUrl(item.file_url)}>Download file</a>}</>}{item.evidence_links?.map((link) => <small key={link} className="link-line">{link} · not opened</small>)}</div></article>)}</div>}</section>
      {isClient && <section className="surface review-card"><div className="section-head"><div><span className="eyebrow">AI ASSISTED REVIEW</span><h2>Assessment</h2><p>Assessment is advisory. It cannot approve this milestone or authorize payment.</p></div></div>{latestReportCurrent && report ? <AssessmentView result={report}/>:<div className="empty-inline"><span>✦</span><div><strong>{milestone.evidence_history?.length ? 'No current assessment' : 'Waiting for evidence'}</strong><p>Run an assessment after the freelancer submits a revision.</p></div></div>}{milestone.evidence_history?.length ? <button className="secondary-button" disabled={busy} onClick={onAssess}>Run assessment for revision {milestone.evidence_revision}</button> : null}{report && milestone.assessment_history?.[0]?.is_stale && <div className="notice-box">This assessment is stale because a newer evidence revision exists.</div>}</section>}
      {isClient && <section className="surface decision-card"><div className="section-head"><div><span className="eyebrow">CLIENT DECISION</span><h2>Your review decision</h2><p>Only the project client can approve or request a revision.</p></div></div><label className="decision-note">Note to freelancer<textarea id="decision-note" rows={2} maxLength={2000} placeholder="What should change or be kept in mind?"/></label><div className="decision-actions"><button className="secondary-button" disabled={busy || !currentReport || milestone.status === 'approved' || milestone.status === 'paid'} onClick={() => onDecision('revision_requested', (document.getElementById('decision-note') as HTMLTextAreaElement).value)}>Request revision</button><button className="primary-button" disabled={busy || !report?.assessment?.all_supported || !currentReport || milestone.status === 'approved' || milestone.status === 'paid'} onClick={() => { if (window.confirm('Approve this milestone based on the current evidence revision?')) onDecision('approved', '') }}>Approve milestone <span>✓</span></button></div>{milestone.status === 'approved' && <button className="text-button revoke-button" disabled={busy || milestone.payment?.status === 'capture_pending' || milestone.payment?.status === 'captured'} onClick={() => { if (window.confirm('Revoke this approval before capture starts?')) onDecision('revoked', 'Client revoked approval') }}>Revoke approval</button>}{milestone.decisions?.length ? <div className="decision-history"><strong>Decision history</strong>{milestone.decisions.slice(0, 5).map((decision, index) => <article key={`${decision.decision}-${decision.created_at}-${index}`}><span>{decision.decision.replaceAll('_', ' ')} · revision {decision.evidence_revision}</span>{decision.note && <p>{decision.note}</p>}<small>{new Date(decision.created_at).toLocaleString()}</small></article>)}</div> : null}</section>}
      <PaymentPanel milestone={milestone} user={user} busy={busy} onOrder={onOrder} onAuthorize={onAuthorize} onCapture={onCapture} onReconcile={onReconcile}/></div>
      <aside className="timeline-column"><section className="surface"><div className="section-head"><div><span className="eyebrow">PROJECT HISTORY</span><h2>Audit timeline</h2></div><button className="icon-button" onClick={onRefresh} title="Refresh timeline" aria-label="Refresh timeline">↻</button></div>{!audit.length ? <p className="muted">Actions will appear here as the project progresses.</p> : <div className="timeline">{audit.map((item, i) => <article className="timeline-item" key={`${item.event_type}-${item.created_at}-${i}`}><span className="timeline-dot"/><div><strong>{item.event_type.replaceAll('.', ' ')}</strong><small>{new Date(item.created_at).toLocaleString()}</small><p>{item.actor_type}</p></div></article>)}</div>}</section><section className="surface trust-card"><span>◈</span><strong>What the assessor can see</strong><p>Only the submitted evidence text and agreed criteria. Links are not opened. Attachments are stored privately but not extracted.</p></section></aside>
    </div>
  </>
}

function AssessmentView({ result }: { result: AssessmentResponse }) {
  const assessment = result.assessment
  if (!assessment) return <div className="assessment-empty"><strong>Assessment could not be completed.</strong><p>{result.trace.error || result.trace.outcome}</p></div>
  return <div className="assessment-report"><div className="report-summary"><span className={`report-indicator ${assessment.all_supported ? 'good' : ''}`}>{assessment.all_supported ? '✓' : '!'}</span><div><strong>{assessment.overall_summary || (assessment.all_supported ? 'All criteria met' : 'Some criteria need follow-up')}</strong><small>Evidence revision {assessment.evidence_revision} · {result.report?.report_version || 'report'} · {result.trace.prompt_version} · {result.trace.model} · {(result.trace.duration_ms / 1000).toFixed(1)}s</small></div></div><div className="finding-list">{assessment.verdicts.map((finding) => <article className="finding" key={finding.criterion_id}><div className="finding-head"><strong>Criterion {finding.criterion_id}</strong><span className={`finding-status ${finding.verdict}`}>{finding.verdict.replaceAll('_',' ')}</span></div>{finding.quote && <blockquote>“{finding.quote}”</blockquote>}<p>{finding.reasoning}</p>{finding.observed_facts?.length > 0 && <small>Observed: {finding.observed_facts.join('; ')}</small>}{finding.model_inferences?.length > 0 && <small>Model inference: {finding.model_inferences.join('; ')}</small>}{finding.missing_or_contradictory?.length > 0 && <small>Missing or contradictory: {finding.missing_or_contradictory.join('; ')}</small>}{finding.recommended_next_action && <small>Next: {finding.recommended_next_action}</small>}</article>)}</div>{(result.report?.limitations || assessment.limitations || []).length > 0 && <div className="limitations"><strong>Limitations</strong><ul>{(result.report?.limitations || assessment.limitations).map((item) => <li key={item}>{item}</li>)}</ul></div>}</div>
}

function PaymentPanel({ milestone, user, busy, onOrder, onAuthorize, onCapture, onReconcile }: { milestone: Milestone; user: User; busy: boolean; onOrder: () => void; onAuthorize: () => void; onCapture: () => void; onReconcile: () => void }) {
  const payment = milestone.payment
  if (user.role !== 'client' && !payment) return null
  return <section className="surface payment-card"><div className="section-head"><div><span className="eyebrow">PAYMENT STATUS</span><h2>PayPal Sandbox</h2></div><span className={`status-chip status-${payment?.status || 'not-created'}`}>{(payment?.status || 'not created').replaceAll('_', ' ')}</span></div><p>{payment ? `${payment.currency} ${payment.amount}` : 'Create a PayPal order for the agreed milestone amount.'}</p>{payment?.paypal_order_id && <small>Order: {payment.paypal_order_id}</small>}{payment?.paypal_authorization_id && <small>Authorization: {payment.paypal_authorization_id}</small>}{payment?.paypal_capture_id && <small>Capture: {payment.paypal_capture_id}</small>}{payment?.status === 'created' && payment.paypal_approval_url && <a className="secondary-button link-button" href={payment.paypal_approval_url} target="_blank" rel="noreferrer">Continue to PayPal ↗</a>}{user.role === 'client' && !payment && <button className="secondary-button" disabled={busy || milestone.status === 'paid'} onClick={onOrder}>Create PayPal order</button>}{user.role === 'client' && payment?.status === 'created' && <button className="secondary-button" disabled={busy} onClick={onAuthorize}>Confirm buyer approval and authorize</button>}{user.role === 'client' && payment?.status === 'authorized' && milestone.status === 'approved' && <button className="primary-button" disabled={busy} onClick={onCapture}>Capture authorized amount <span>→</span></button>}{user.role === 'client' && payment?.status === 'capture_pending' && <button className="secondary-button" disabled={busy} onClick={onReconcile}>Reconcile with PayPal</button>}{payment?.status === 'captured' && <p className="payment-complete">Capture confirmed · {payment.paypal_capture_id}</p>}<small>TrustFlow coordinates this PayPal transaction; it does not provide legal escrow.</small></section>
}

export default App
