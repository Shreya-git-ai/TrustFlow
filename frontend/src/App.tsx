import { lazy, Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import {
  acceptProject, assessMilestone, authorizePayment, capturePayment, createMilestone, evidenceFileUrl,
  createPaymentOrder, createProject, currentUser, decideMilestone, decideRefundProposal, getAudit, getMilestone, getPayments, getRefundProposals, getWorkspaceActivity,
  getProject, getProjects, login, logout, reconcilePayment, requestPasswordReset, resendVerification, resetPassword, signup, submitEvidence,
  updateAccount, updateMilestone, verifyEmail,
  type AssessmentResponse, type Milestone, type Project, type RefundProposal, type User, type WorkspaceActivity, type WorkspacePayment,
} from './api/assessment'
import NotificationCenter from './components/audit/NotificationCenter'
import NotificationPreferencesCard from './components/audit/NotificationPreferences'
import { buildNotifications, defaultNotificationPreferences, savedNotificationPreferences, type NotificationPreferences, type WorkspaceNotification } from './components/audit/notificationData'
import RecentActivity from './components/audit/RecentActivity'
import PaymentsPage from './components/payments/PaymentsPage'
import InsightsPage from './pages/InsightsPage'
import ResourcesPage from './pages/ResourcesPage'
import TeamDirectoryPage from './pages/TeamDirectoryPage'
import './App.css'

type AuthMode = 'login' | 'signup'
type WorkspaceSection = 'overview' | 'payments' | 'insights' | 'resources' | 'team'
const ProjectsGrid = lazy(() => import('./components/dashboard/ProjectsGrid'))

function savedNotificationIds(userId: string) {
  try {
    const saved = JSON.parse(window.localStorage.getItem(`trustflow.notifications.read.${userId}`) || '[]')
    return Array.isArray(saved) ? saved.filter((id): id is string => typeof id === 'string') : []
  } catch {
    return []
  }
}

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [projects, setProjects] = useState<Project[]>([])
  const [project, setProject] = useState<Project | null>(null)
  const [milestone, setMilestone] = useState<Milestone | null>(null)
  const [audit, setAudit] = useState<Awaited<ReturnType<typeof getAudit>>>([])
  const [activity, setActivity] = useState<WorkspaceActivity[]>([])
  const [activityLoading, setActivityLoading] = useState(false)
  const [activityError, setActivityError] = useState('')
  const [payments, setPayments] = useState<WorkspacePayment[]>([])
  const [paymentsLoading, setPaymentsLoading] = useState(false)
  const [paymentsError, setPaymentsError] = useState('')
  const [refundProposals, setRefundProposals] = useState<RefundProposal[]>([])
  const [refundProposalsLoading, setRefundProposalsLoading] = useState(false)
  const [refundProposalsError, setRefundProposalsError] = useState('')
  const [busy, setBusy] = useState(false)
  const operationCount = useRef(0)
  const [initializing, setInitializing] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(() => {
    if (window.location.pathname === '/payment-return') return 'PayPal returned you to TrustFlow. Confirm buyer approval to authorize the milestone payment.'
    if (window.location.pathname === '/payment-cancel') return 'PayPal checkout was cancelled. The payment remains unchanged.'
    return ''
  })
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [activeSection, setActiveSection] = useState<WorkspaceSection>('overview')
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try { return JSON.parse(window.localStorage.getItem('trustflow.sidebar.collapsed') || 'false') === true } catch { return false }
  })
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [notificationsRead, setNotificationsRead] = useState<string[]>([])
  const [notificationPreferences, setNotificationPreferences] = useState<NotificationPreferences>(defaultNotificationPreferences)
  const [searchQuery, setSearchQuery] = useState('')
  const accountMenuRef = useRef<HTMLDivElement | null>(null)
  const notificationsRef = useRef<HTMLDivElement | null>(null)
  const [pendingVerificationEmail, setPendingVerificationEmail] = useState('')
  const [pendingVerificationMessage, setPendingVerificationMessage] = useState('')
  const [verificationStatus, setVerificationStatus] = useState<'checking' | 'verified' | 'error' | null>(() => {
    if (window.location.pathname !== '/verify-email') return null
    return window.location.hash.length > 1 ? 'checking' : 'error'
  })
  const loadProjects = useCallback(async () => setProjects(await getProjects()), [])
  const loadActivity = useCallback(async () => {
    setActivityLoading(true)
    setActivityError('')
    try {
      setActivity(await getWorkspaceActivity())
    } catch (e) {
      setActivityError(e instanceof Error ? e.message : 'Could not load workspace activity.')
    } finally {
      setActivityLoading(false)
    }
  }, [])
  const loadPayments = useCallback(async () => {
    setPaymentsLoading(true)
    setPaymentsError('')
    setRefundProposalsLoading(user?.role === 'client')
    setRefundProposalsError('')
    const [paymentResult, proposalResult] = await Promise.allSettled([
      getPayments(),
      user?.role === 'client' ? getRefundProposals() : Promise.resolve<RefundProposal[]>([]),
    ])
    if (paymentResult.status === 'fulfilled') setPayments(paymentResult.value)
    else setPaymentsError(paymentResult.reason instanceof Error ? paymentResult.reason.message : 'Could not load payment records.')
    if (proposalResult.status === 'fulfilled') setRefundProposals(proposalResult.value)
    else setRefundProposalsError(proposalResult.reason instanceof Error ? proposalResult.reason.message : 'Could not load refund proposals.')
    setPaymentsLoading(false)
    setRefundProposalsLoading(false)
  }, [user])
  useEffect(() => {
    function closeFloatingMenus(event: MouseEvent) {
      if (accountMenuRef.current && !accountMenuRef.current.contains(event.target as Node)) setAccountMenuOpen(false)
      if (notificationsRef.current && !notificationsRef.current.contains(event.target as Node)) setNotificationsOpen(false)
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') { setAccountMenuOpen(false); setNotificationsOpen(false) }
    }
    document.addEventListener('mousedown', closeFloatingMenus)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeFloatingMenus)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [])

  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== 'k') return
      const input = document.querySelector<HTMLInputElement>('.topbar-search input')
      if (!input) return
      event.preventDefault()
      input.focus()
      input.select()
    }
    document.addEventListener('keydown', focusSearch)
    return () => document.removeEventListener('keydown', focusSearch)
  }, [])
  useEffect(() => {
    let active = true

    async function initialize() {
      try {
        const response = await currentUser()
        if (!active) return
        setUser(response.user)
        setNotificationsRead(savedNotificationIds(response.user.id))
        setNotificationPreferences(savedNotificationPreferences(response.user.id))

        // Project loading is independent from authentication. A project API
        // failure should not incorrectly sign out an otherwise valid session.
        try {
          const loadedProjects = await getProjects()
          if (active) setProjects(loadedProjects)
        } catch (e) {
          if (active) setError(e instanceof Error ? e.message : 'Could not load projects.')
        }
        if (active) void loadActivity()
      } catch (e) {
        if (!active) return
        setUser(null)
        if (e instanceof Error && e.message !== 'Authentication required') setError(e.message)
      } finally {
        if (active) setInitializing(false)
      }
    }

    void initialize()
    return () => { active = false }
  }, [loadActivity])

  useEffect(() => {
    if (!user) return
    const params = new URLSearchParams(window.location.search)
    const projectId = params.get('project_id') ?? ''
    const milestoneId = params.get('milestone_id') ?? ''
    if (!projectId || !milestoneId) return

    let active = true
    async function openLinkedMilestone() {
      try {
        const [selectedProject, selectedMilestone] = await Promise.all([
          getProject(projectId),
          getMilestone(milestoneId),
        ])
        if (selectedMilestone.project_id !== selectedProject.id) throw new Error('Link mismatch')
        const selectedAudit = await getAudit(projectId)
        if (!active) return
        setProject(selectedProject)
        setMilestone(selectedMilestone)
        setAudit(selectedAudit)
        setSettingsOpen(false)
        setActiveSection('overview')
      } catch {
        if (active) setError('This milestone link is unavailable or your account cannot access it.')
      } finally {
        if (active) window.history.replaceState({}, '', window.location.pathname)
      }
    }
    void openLinkedMilestone()
    return () => { active = false }
  }, [user])

  useEffect(() => {
    if (window.location.pathname !== '/verify-email') return
    let active = true
    const token = window.location.hash.slice(1)
    if (!token) {
      return () => { active = false }
    }
    verifyEmail(token).then(() => {
      if (active) {
        window.history.replaceState({}, '', '/verify-email')
        setVerificationStatus('verified')
      }
    }).catch(() => {
      if (active) {
        window.history.replaceState({}, '', '/verify-email')
        setVerificationStatus('error')
      }
    })
    return () => { active = false }
  }, [])

  function beginOperation() {
    operationCount.current += 1
    setBusy(true)
  }

  function endOperation() {
    operationCount.current = Math.max(0, operationCount.current - 1)
    setBusy(operationCount.current > 0)
  }

  async function run(action: () => Promise<void>): Promise<boolean> {
    beginOperation()
    setError('')
    setNotice('')
    try {
      await action()
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The request failed.')
      return false
    } finally {
      endOperation()
    }
  }

  async function openProject(id: string) {
    await run(async () => {
      const selected = await getProject(id)
      setSettingsOpen(false)
      setActiveSection('overview')
      setProject(selected); setMilestone(null); setAudit(await getAudit(id))
    })
  }

  async function editProjectMilestone(id: string) {
    await run(async () => {
      const selected = await getProject(id)
      const editableMilestoneSummary = selected.milestones?.find((item) => item.status === 'pending')
      const [editableMilestone, selectedAudit] = await Promise.all([
        editableMilestoneSummary ? getMilestone(editableMilestoneSummary.id) : Promise.resolve(null),
        getAudit(id),
      ])
      setSettingsOpen(false)
      setActiveSection('overview')
      setProject(selected)
      setMilestone(editableMilestone)
      setAudit(selectedAudit)
    })
  }

  async function openWorkspaceActivity(item: WorkspaceActivity) {
    await run(async () => {
      const selected = await getProject(item.project_id)
      const selectedMilestone = item.milestone_id ? await getMilestone(item.milestone_id) : null
      setSettingsOpen(false); setActiveSection('overview')
      setProject(selected); setMilestone(selectedMilestone); setAudit(await getAudit(item.project_id))
    })
  }

  function toggleSidebar() {
    setSidebarCollapsed((collapsed) => {
      const next = !collapsed
      try { window.localStorage.setItem('trustflow.sidebar.collapsed', JSON.stringify(next)) } catch { /* collapse state remains for this session */ }
      return next
    })
  }

  function openSettings() {
    setProject(null); setMilestone(null); setSettingsOpen(true); setActiveSection('overview')
    setAccountMenuOpen(false); setNotificationsOpen(false)
  }

  async function openPaymentMilestone(payment: WorkspacePayment) {
    await run(async () => {
      const selected = await getProject(payment.project_id)
      const selectedMilestone = await getMilestone(payment.milestone_id)
      setSettingsOpen(false); setActiveSection('overview')
      setProject(selected); setMilestone(selectedMilestone); setAudit(await getAudit(payment.project_id))
    })
  }

  function reviewRefundProposal(proposal: RefundProposal, decision: 'approve' | 'reject') {
    if (decision === 'approve') {
      const prompt = proposal.status === 'processing'
        ? 'Retry the same PayPal refund request to check its status? PayPal receives the same idempotency key.'
        : `Approve a ${proposal.currency} ${proposal.amount} refund to the original PayPal payment?`
      if (!window.confirm(prompt)) return
    }
    if (decision === 'reject' && !window.confirm('Reject this agent-proposed refund?')) return
    void run(async () => {
      try {
        const result = await decideRefundProposal(proposal.id, decision)
        if (decision === 'reject') setNotice('Refund proposal rejected.')
        else if (result.status === 'refunded') setNotice('PayPal confirmed the refund. Support automation will run after the verified webhook is processed.')
        else setNotice('Refund approved. PayPal is processing it; support automation will run after the verified completion webhook.')
      } finally {
        await loadPayments()
      }
    })
  }

  function navigateSection(section: WorkspaceSection) {
    setProject(null); setMilestone(null); setSettingsOpen(false); setActiveSection(section)
    setAccountMenuOpen(false); setNotificationsOpen(false)
    if (section === 'payments') void loadPayments()
  }

  function markNotificationsRead(ids: string[]) {
    if (!user) return
    const next = [...new Set([...notificationsRead, ...ids])]
    setNotificationsRead(next)
    try { window.localStorage.setItem(`trustflow.notifications.read.${user.id}`, JSON.stringify(next)) } catch { /* read state remains available for this session */ }
  }

  function saveNotificationPreferences(preferences: NotificationPreferences) {
    setNotificationPreferences(preferences)
    if (!user) return
    try { window.localStorage.setItem(`trustflow.notifications.preferences.${user.id}`, JSON.stringify(preferences)) } catch { /* preferences remain active for this session */ }
  }

  function openNotification(item: WorkspaceNotification) {
    markNotificationsRead([item.id])
    if (item.destination === 'payments') navigateSection('payments')
    else if (item.projectId) void openProject(item.projectId)
    setNotificationsOpen(false)
  }

  async function refreshSelected() {
    if (!project) return
    const selected = await getProject(project.id)
    setProject(selected)
    setProjects(await getProjects())
    if (milestone) setMilestone(await getMilestone(milestone.id))
    setAudit(await getAudit(project.id))
    await loadActivity()
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
        setNotificationsRead(savedNotificationIds(response.user.id))
        setNotificationPreferences(savedNotificationPreferences(response.user.id))
        setProjects(await getProjects())
        void loadActivity()
        setNotice('Account created. Email confirmation is disabled in this development environment.')
      } else {
        const email = String(values.get('email'))
        let response: Awaited<ReturnType<typeof login>>
        try {
          response = await login({ email, password: String(values.get('password')) })
        } catch (error) {
          if (error instanceof Error && error.message === 'Confirm your email before signing in') {
            setPendingVerificationEmail(email)
            setPendingVerificationMessage('Confirm your email before signing in. You can request a fresh link below.')
            return
          }
          throw error
        }
        setUser(response.user)
        setNotificationsRead(savedNotificationIds(response.user.id))
        setNotificationPreferences(savedNotificationPreferences(response.user.id))
        setProjects(await getProjects())
        void loadActivity()
      }
    })
  }

  async function resendConfirmation(email: string): Promise<string> {
    beginOperation()
    setError('')
    try {
      const response = await resendVerification(email)
      setPendingVerificationMessage(response.message)
      return response.message
    } catch (e) {
      const message = e instanceof Error ? e.message : 'The request failed.'
      setError(message)
      return ''
    } finally {
      endOperation()
    }
  }

  async function signOut() {
    await run(async () => { await logout(); setUser(null); setNotificationsRead([]); setProject(null); setMilestone(null); setProjects([]); setActivity([]); setPayments([]); setRefundProposals([]); setSettingsOpen(false); setActiveSection('overview') })
  }

  if (window.location.pathname === '/verify-email') return <EmailVerificationPage status={verificationStatus || 'checking'} onResend={resendConfirmation} busy={busy} error={error} />
  if (window.location.pathname === '/forgot-password') return <ForgotPasswordPage />
  if (window.location.pathname === '/reset-password') return <ResetPasswordPage />
  if (pendingVerificationEmail) return <VerificationPending email={pendingVerificationEmail} message={pendingVerificationMessage} busy={busy} error={error} onResend={resendConfirmation} onBack={() => { setPendingVerificationEmail(''); setAuthMode('login'); setError('') }} />
  if (!['/', '/payment-return', '/payment-cancel'].includes(window.location.pathname)) return <main className="not-found-page"><section className="surface"><span className="eyebrow">404 · PAGE NOT FOUND</span><h1>We couldn’t find that page.</h1><p>Use your workspace navigation to return to a project.</p><a className="primary-button link-button" href="/">Go to TrustFlow</a></section></main>
  if (initializing) return <main className="app-loading" role="status" aria-live="polite"><span className="verification-spinner" aria-hidden="true"/><p>Loading TrustFlow…</p></main>
  if (!user) return <AuthScreen mode={authMode} setMode={setAuthMode} onSubmit={handleAuth} busy={busy} error={error} />

  const activePayments = projects.reduce((sum, item) => sum + (item.active_payment_count || 0), 0)
  const notificationItems = buildNotifications(projects, user.role, notificationPreferences)
  const sectionTitle = activeSection === 'payments' ? 'Payments' : activeSection === 'insights' ? 'Insights' : activeSection === 'resources' ? 'Resources' : activeSection === 'team' ? 'Team Directory' : 'Overview'

  return <div className="app-shell" data-sidebar={sidebarCollapsed ? 'collapsed' : 'expanded'}>
    <aside className="sidebar">
      <div className="sidebar-brand-zone">
        <a className="brand sidebar-brand" href="/" aria-label="TrustFlow home"><span className="brand-mark">T</span><span>trustflow<span className="brand-dot">.</span></span></a>
        <button type="button" className="sidebar-collapse-toggle" aria-label={sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'} title={sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'} aria-expanded={!sidebarCollapsed} onClick={toggleSidebar}><span className="sidebar-collapse-chevron" aria-hidden="true">‹</span></button>
      </div>
      <div className="workspace-chip"><span className="workspace-avatar">{user.name.trim().slice(0, 1).toUpperCase()}</span><span className="workspace-chip-copy"><small>YOUR WORKSPACE</small><strong>{user.role === 'client' ? 'Client studio' : 'Freelancer desk'}</strong><em><i /> Personal workspace</em></span><span className="workspace-chevron">⌄</span></div>
      <p className="nav-caption">WORKSPACE</p>
      <button className={`nav-link ${!project && !settingsOpen && activeSection === 'overview' ? 'selected' : ''}`} aria-label="Overview" title="Overview" onClick={() => navigateSection('overview')}><span aria-hidden="true">▦</span><span className="nav-label">Overview</span><kbd>01</kbd></button>
      {project && <button className="nav-link selected" aria-label="Project details" title="Project details" onClick={() => { setMilestone(null); void openProject(project.id) }}><span aria-hidden="true">◇</span><span className="nav-label">Project details</span></button>}
      <p className="nav-caption nav-caption-spaced">WORKFLOW <span>LIVE</span></p>
      <button className={`nav-link ${!project && !settingsOpen && activeSection === 'payments' ? 'selected' : ''}`} aria-label="Payments" title="Payments" aria-current={!project && activeSection === 'payments' ? 'page' : undefined} onClick={() => navigateSection('payments')}><span aria-hidden="true">↗</span><span className="nav-label">Payments</span>{activePayments > 0 && <span className="nav-live-count">{activePayments}</span>}</button>
      <button className={`nav-link ${!project && !settingsOpen && activeSection === 'insights' ? 'selected' : ''}`} aria-label="Insights" title="Insights" aria-current={!project && activeSection === 'insights' ? 'page' : undefined} onClick={() => navigateSection('insights')}><span aria-hidden="true">▥</span><span className="nav-label">Insights</span></button>
      <button className={`nav-link ${!project && !settingsOpen && activeSection === 'resources' ? 'selected' : ''}`} aria-label="Resources" title="Resources" aria-current={!project && activeSection === 'resources' ? 'page' : undefined} onClick={() => navigateSection('resources')}><span aria-hidden="true">⌘</span><span className="nav-label">Resources</span></button>
      <button className={`nav-link ${!project && !settingsOpen && activeSection === 'team' ? 'selected' : ''}`} aria-label="Team Directory" title="Team Directory" aria-current={!project && activeSection === 'team' ? 'page' : undefined} onClick={() => navigateSection('team')}><span aria-hidden="true">♧</span><span className="nav-label">Team Directory</span></button>
      <div className="sidebar-bottom">
        <div className="sidebar-payments-card"><div className="sidebar-payments-kicker"><span className="tiny-shield">✓</span> PAYMENT PARTNER</div><img src="/paypal-logo.svg" alt="PayPal"/><strong>Payments with a paper trail.</strong><p>Clear agreements. Visible evidence. Human approval.</p><span className="sidebar-preview-pill">TRUSTFLOW PRINCIPLE</span></div>
        <div className="sidebar-account-mini"><span className="sidebar-account-avatar">{user.name.trim().slice(0, 1).toUpperCase()}</span><span className="sidebar-account-copy"><strong>{user.name}</strong><small>{user.role === 'client' ? 'Client account' : 'Freelancer account'}</small></span><button type="button" aria-label="Open account settings" title="Account settings" onClick={openSettings}>⚙</button></div>
      </div>
    </aside>
    <main className="main-area">
      <header className="topbar">
        <div className="topbar-context-area">
          <a className="brand topbar-mobile-brand" href="/" aria-label="TrustFlow home"><span className="brand-mark">T</span><span>trustflow<span className="brand-dot">.</span></span></a>
          <div className="topbar-context"><span className="context-icon" aria-hidden="true">{settingsOpen ? '⚙' : milestone ? '◇' : project ? '↗' : activeSection === 'payments' ? '$' : activeSection === 'insights' ? '▥' : activeSection === 'resources' ? '⌘' : activeSection === 'team' ? '♧' : '⌂'}</span><div><small>{settingsOpen ? 'ACCOUNT / PREFERENCES' : project ? 'WORKSPACE / PROJECTS' : activeSection === 'overview' ? 'YOUR WORKSPACE' : `WORKSPACE / ${sectionTitle.toUpperCase()}`}</small><strong>{settingsOpen ? 'Account settings' : milestone ? milestone.title : project ? project.title : sectionTitle}</strong></div></div>
          {!settingsOpen && !project && activeSection === 'overview' && <label className="topbar-search"><span aria-hidden="true">⌕</span><input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} aria-label="Search projects" placeholder="Search projects…"/><kbd>⌘ K</kbd></label>}
        </div>
        <div className="topbar-actions">
          <div className="paypal-header-lockup topbar-paypal" aria-label="Powered by PayPal"><span className="powered-by">POWERED BY</span><img className="paypal-logo" src="/paypal-logo.svg" alt="PayPal"/></div>
          <div ref={notificationsRef}><NotificationCenter projects={projects} role={user.role} preferences={notificationPreferences} open={notificationsOpen} readIds={notificationsRead} onToggle={() => { setNotificationsOpen((open) => !open); setAccountMenuOpen(false) }} onMarkAllRead={() => markNotificationsRead(notificationItems.map((item) => item.id))} onSelect={openNotification}/></div>
          <div className="account-menu-wrap" ref={accountMenuRef}>
            <button className={`account-trigger ${accountMenuOpen ? 'is-open' : ''}`} aria-label="Open account menu" aria-haspopup="menu" aria-expanded={accountMenuOpen} onClick={() => { setAccountMenuOpen((open) => !open); setNotificationsOpen(false) }}>
              <span className="account-trigger-avatar">{user.name.trim().slice(0, 1).toUpperCase()}</span><span className="account-trigger-copy"><strong>{user.name}</strong><small>{user.role === 'client' ? 'Client account' : 'Freelancer account'}</small></span><span className="account-chevron" aria-hidden="true">⌄</span>
            </button>
            {accountMenuOpen && <div className="account-dropdown" role="menu">
              <div className="account-dropdown-profile"><span className="account-trigger-avatar large">{user.name.trim().slice(0, 1).toUpperCase()}</span><div><small>YOUR TRUSTFLOW ACCOUNT</small><strong>{user.name}</strong><span className="account-role-pill">{user.role === 'client' ? 'CLIENT' : 'FREELANCER'}</span></div></div>
              <div className="account-detail-block"><span className="account-detail-label">EMAIL ADDRESS</span><strong className="account-email-value">{user.email}</strong><span className={`account-verification-state ${user.email_verified ? 'verified' : 'pending'}`}><i />{user.email_verified ? 'Email verified' : 'Email verification pending'}</span></div>
              {user.role === 'client' && ((user as User & { company_name?: string | null; company?: string | null; business_name?: string | null }).company_name || (user as User & { company_name?: string | null; company?: string | null; business_name?: string | null }).company || (user as User & { company_name?: string | null; company?: string | null; business_name?: string | null }).business_name) && <div className="account-company"><span>COMPANY / ORGANISATION</span><strong>{(user as User & { company_name?: string | null; company?: string | null; business_name?: string | null }).company_name || (user as User & { company_name?: string | null; company?: string | null; business_name?: string | null }).company || (user as User & { company_name?: string | null; company?: string | null; business_name?: string | null }).business_name}</strong></div>}
              <div className="account-security-summary"><span className="account-security-icon">♢</span><div><strong>Account security</strong><small>{user.email_verified ? 'Your email is confirmed.' : 'Confirm your email to finish account setup.'}</small></div><span className={`security-state ${user.email_verified ? 'good' : 'attention'}`}>{user.email_verified ? 'GOOD' : 'ACTION'}</span></div>
              <div className="account-dropdown-divider" />
              <button role="menuitem" className="account-dropdown-item" onClick={openSettings}><span aria-hidden="true">⚙</span>Account settings <i>Manage profile & security</i></button>
              <button role="menuitem" className="account-dropdown-item danger" disabled={busy} onClick={() => { setAccountMenuOpen(false); void signOut() }}><span aria-hidden="true">↗</span>Log out <i>End this session</i></button>
            </div>}
          </div>
        </div>
      </header>
      <div className="content">
        {error && <div role="alert" className="alert error-alert"><strong>Could not complete that action.</strong> {error}<button onClick={() => setError('')} aria-label="Dismiss">×</button></div>}
        {notice && <div role="status" className="alert success-alert">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss">×</button></div>}
        {!project && settingsOpen && <SettingsPage user={user} busy={busy} notificationPreferences={notificationPreferences} onPreferenceChange={saveNotificationPreferences} onSave={(data) => void run(async () => { const response = await updateAccount(data); setUser(response.user); setNotice('Account settings saved. Your session was rotated.') })} />}
        {!project && !settingsOpen && activeSection === 'overview' && <Dashboard
          user={user} projects={projects} busy={busy} searchQuery={searchQuery} activity={activity}
          activityLoading={activityLoading} activityError={activityError} onOpen={openProject} onEditProject={editProjectMilestone} onClearSearch={() => setSearchQuery('')}
          onOpenInsights={() => navigateSection('insights')} onOpenResources={() => navigateSection('resources')} onOpenActivity={openWorkspaceActivity}
          onAccept={(id) => void run(async () => { await acceptProject(id); await loadProjects(); await loadActivity(); setNotice('Project invitation accepted.') })}
          onCreate={(data) => run(async () => { await createProject(data); await loadProjects(); await loadActivity(); setNotice('Project created. The freelancer can accept the invitation from their workspace. Email delivery depends on SMTP or a Zapier email action.') })}
        />}
        {!project && !settingsOpen && activeSection === 'payments' && <PaymentsPage
          payments={payments} paymentsLoading={paymentsLoading} paymentsError={paymentsError}
          proposals={refundProposals} proposalsLoading={refundProposalsLoading} proposalsError={refundProposalsError}
          role={user.role} busy={busy} onRefresh={() => void loadPayments()}
          onOpenMilestone={(payment) => void openPaymentMilestone(payment)} onOverview={() => navigateSection('overview')}
          onRefundApprove={(proposal) => reviewRefundProposal(proposal, 'approve')}
          onRefundReject={(proposal) => reviewRefundProposal(proposal, 'reject')}
        />}
        {!project && !settingsOpen && activeSection === 'insights' && <InsightsPage projects={projects} role={user.role} activity={activity} loading={activityLoading} error={activityError} onRefresh={() => void loadActivity()} onOpenProject={(id) => void openProject(id)} onOpenActivity={(item) => void openWorkspaceActivity(item)}/>}
        {!project && !settingsOpen && activeSection === 'resources' && <ResourcesPage role={user.role} projects={projects} onOverview={() => navigateSection('overview')} onPayments={() => navigateSection('payments')} onOpenProject={(id) => void openProject(id)} onTeamDirectory={() => navigateSection('team')}/>}
        {!project && !settingsOpen && activeSection === 'team' && <TeamDirectoryPage projects={projects} role={user.role} onOpenProject={(id) => void openProject(id)}/>}
        {project && milestone && <MilestonePage
          milestone={milestone} project={project} user={user} busy={busy} audit={audit}
          onBack={() => setMilestone(null)} onRefresh={() => void run(refreshSelected)}
          onUpdate={(data) => run(async () => { await updateMilestone(project.id, milestone.id, data); await refreshSelected(); setNotice('Milestone terms updated.') })}
          onEvidence={(description, links, file) => run(async () => { await submitEvidence(milestone.id, description, links, file); await refreshSelected(); setNotice('Evidence revision submitted. A client can now request an assessment.') })}
          onAssess={() => void run(async () => { const report = await assessMilestone(milestone.id); await refreshSelected(); setNotice(report.stale ? 'Assessment saved, but the evidence changed while it was running. Review the latest revision.' : 'Assessment report saved to project history.') })}
          onDecision={(decision, note) => void run(async () => { await decideMilestone(milestone.id, decision, note); await refreshSelected(); setNotice(decision === 'approved' ? 'Milestone approved by the client.' : decision === 'revoked' ? 'Approval revoked.' : 'Revision requested.') })}
          onOrder={() => void run(async () => { await createPaymentOrder(milestone.id); await refreshSelected(); setNotice('PayPal order created. Use the Continue to PayPal link below, then return here to authorize it.') })}
          onAuthorize={() => void run(async () => { await authorizePayment(milestone.id); await refreshSelected(); setNotice('PayPal authorization confirmed.') })}
          onCapture={() => void run(async () => { if (!window.confirm('Capture the authorized milestone amount from PayPal?')) return; const result = await capturePayment(milestone.id); await refreshSelected(); setNotice(result.status === 'captured' ? 'PayPal confirmed the capture.' : 'Capture is pending. TrustFlow will not submit another capture until PayPal is reconciled.') })}
          onReconcile={() => void run(async () => { const result = await reconcilePayment(milestone.id); await refreshSelected(); setNotice(result.status === 'captured' ? 'PayPal confirmed the capture.' : 'PayPal still has no completed capture to report.') })}
        />}
        {project && !milestone && <ProjectPage project={project} user={user} busy={busy} onBack={() => { setProject(null); setMilestone(null) }} onSelect={selectMilestone} onCreateMilestone={(data) => run(async () => { await createMilestone(project.id, data); await refreshSelected(); setNotice('Milestone added to the project.') })}/>}
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
      {mode === 'login' && <a className="auth-forgot-password" href="/forgot-password">Forgot password?</a>}
      <p className="auth-limit">Email confirmation is enabled when delivery is configured. Password resets use a one-time email link.</p>
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
    const form = event.currentTarget
    const email = (initialEmail || String(new FormData(form).get('email') || '')).trim()
    if (!email) {
      setMessage('Enter the email address used for your account.')
      return
    }
    setMessage(await onResend(email))
  }
  return <form className="resend-form" onSubmit={(event) => void submit(event)}>
    {!initialEmail && <label>Email<input name="email" type="email" autoComplete="email" required maxLength={254}/></label>}
    <button className="secondary-button" disabled={busy}>{busy ? 'Sending…' : 'Resend confirmation email'}</button>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {message && <p className="resend-message" role="status">{message}</p>}
  </form>
}

function ForgotPasswordPage() {
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const email = String(new FormData(event.currentTarget).get('email') || '').trim()
      await requestPasswordReset(email)
      setSent(true)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The request could not be completed.')
    } finally {
      setBusy(false)
    }
  }

  return <main className="verification-page auth-enter"><section className="verification-card surface">
    <span className="verification-icon">↻</span><span className="eyebrow">ACCOUNT RECOVERY</span><h1>Reset your password</h1>
    {sent ? <><p role="status">If a verified account uses that email and email delivery is configured, a reset link will arrive shortly. Check your spam folder too.</p><a className="primary-button link-button" href="/">Return to sign in <span>→</span></a></> : <>
      <p>Enter the email address on your TrustFlow account. We’ll send a one-time reset link if the account is eligible and email delivery is configured.</p>
      <form className="resend-form" onSubmit={(event) => void submit(event)}><label>Email<input name="email" type="email" autoComplete="email" required maxLength={254}/></label><button className="primary-button" disabled={busy}>{busy ? 'Sending…' : 'Send reset link'} <span>→</span></button>{error && <p className="inline-error" role="alert">{error}</p>}</form>
      <a className="text-button verification-back" href="/">Back to sign in</a>
    </>}
  </section></main>
}

function ResetPasswordPage() {
  const [busy, setBusy] = useState(false)
  const [complete, setComplete] = useState(false)
  const [error, setError] = useState('')
  const token = window.location.hash.slice(1)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    const password = String(values.get('password') || '')
    if (password !== String(values.get('confirm_password') || '')) {
      setError('The passwords do not match.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await resetPassword(token, password)
      window.history.replaceState({}, '', '/reset-password')
      setComplete(true)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The password could not be reset.')
    } finally {
      setBusy(false)
    }
  }

  return <main className="verification-page auth-enter"><section className="verification-card surface">
    <span className={`verification-icon ${complete ? 'verified' : token ? '' : 'invalid'}`}>{complete ? '✓' : token ? '↻' : '!'}</span>
    <span className="eyebrow">ACCOUNT RECOVERY</span>
    {complete ? <><h1>Password updated</h1><p>Your password has been changed and other sessions have been signed out.</p><a className="primary-button link-button" href="/">Sign in with your new password <span>→</span></a></> : !token ? <><h1>Reset link unavailable</h1><p>This link is missing or has already been removed from the address.</p><a className="primary-button link-button" href="/forgot-password">Request another link <span>→</span></a></> : <><h1>Choose a new password</h1><p>Use at least 12 characters. This link expires after 30 minutes and can only be used once.</p>
      <form className="resend-form reset-password-form" onSubmit={(event) => void submit(event)}><PasswordField label="New password" name="password" autoComplete="new-password" required minLength={12} maxLength={128}/><PasswordField label="Confirm new password" name="confirm_password" autoComplete="new-password" required minLength={12} maxLength={128}/>{error && <p className="inline-error" role="alert">{error}</p>}<button className="primary-button" disabled={busy}>{busy ? 'Updating…' : 'Update password'} <span>→</span></button></form>
    </>}
  </section></main>
}

function Dashboard({ user, projects, busy, searchQuery, activity, activityLoading, activityError, onOpen, onEditProject, onClearSearch, onOpenInsights, onOpenResources, onOpenActivity, onAccept, onCreate }: {
  user: User; projects: Project[]; busy: boolean; searchQuery: string; activity: WorkspaceActivity[]
  activityLoading: boolean; activityError: string; onOpen: (id: string) => void; onEditProject: (id: string) => void; onClearSearch: () => void
  onOpenInsights: () => void; onOpenResources: () => void; onOpenActivity: (item: WorkspaceActivity) => void
  onAccept: (id: string) => void
  onCreate: (data: { title: string; description: string; currency: string; freelancer_email: string }) => Promise<boolean>
}) {
  const [projectFilter, setProjectFilter] = useState<'all' | 'active' | 'invited'>('all')
  const [attentionOnly, setAttentionOnly] = useState(false)
  const [sortBy, setSortBy] = useState<'recent' | 'name' | 'attention'>('recent')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const query = searchQuery.trim().toLowerCase()
  const projectActivity = new Map<string, WorkspaceActivity>()
  for (const item of activity) {
    const previous = projectActivity.get(item.project_id)
    if (!previous || new Date(item.created_at).getTime() > new Date(previous.created_at).getTime()) projectActivity.set(item.project_id, item)
  }
  const matchedProjects = projects.filter((item) => {
    const matchesQuery = !query || `${item.title} ${item.description || ''} ${item.client_name || ''} ${item.freelancer_name || ''}`.toLowerCase().includes(query)
    const matchesFilter = projectFilter === 'all' || (projectFilter === 'invited' ? item.membership_status === 'invited' : item.membership_status === 'accepted')
    const hasAttention = item.membership_status === 'invited' || Boolean(item.submitted_count || item.revision_count || item.decision_due_count)
    return matchesQuery && matchesFilter && (!attentionOnly || hasAttention)
  })
  const filteredProjects = [...matchedProjects].sort((left, right) => {
    if (sortBy === 'name') return left.title.localeCompare(right.title)
    if (sortBy === 'attention') {
      const leftAttention = left.membership_status === 'invited' ? 1 : user.role === 'client' ? Math.max(left.submitted_count || 0, left.decision_due_count || 0) : left.revision_count || 0
      const rightAttention = right.membership_status === 'invited' ? 1 : user.role === 'client' ? Math.max(right.submitted_count || 0, right.decision_due_count || 0) : right.revision_count || 0
      return rightAttention - leftAttention || left.title.localeCompare(right.title)
    }
    return new Date(projectActivity.get(right.id)?.created_at || 0).getTime() - new Date(projectActivity.get(left.id)?.created_at || 0).getTime()
  })
  const activeCount = projects.filter((item) => item.membership_status === 'accepted').length
  const invitationCount = projects.filter((item) => item.membership_status === 'invited').length
  const attentionProjectCount = projects.filter((item) => item.membership_status === 'accepted' && Boolean(item.submitted_count || item.revision_count || item.decision_due_count)).length
  const dueCount = projects.reduce((sum, item) => sum + (item.decision_due_count || 0), 0)
  const milestoneCount = projects.reduce((sum, item) => sum + (item.milestone_count || 0), 0)
  const progressPoints = projects.reduce((sum, item) => sum + (item.progress_percent || 0) * (item.milestone_count || 0), 0)
  const overallProgress = milestoneCount ? Math.round(progressPoints / milestoneCount) : 0
  const pipelineBuckets = [
    { label: 'On track', count: Math.max(0, activeCount - attentionProjectCount), color: '#5545a9' },
    { label: 'Needs attention', count: attentionProjectCount, color: '#e5ad4d' },
    { label: 'Invitations', count: invitationCount, color: '#56a9a2' },
    { label: 'Other', count: Math.max(0, projects.length - activeCount - invitationCount), color: '#c9cbd5' },
  ]
  const pipelineTotal = pipelineBuckets.reduce((sum, item) => sum + item.count, 0)
  let pipelineCursor = 0
  const pipelineGradient = pipelineBuckets.map((item) => {
    const start = pipelineCursor
    pipelineCursor += pipelineTotal ? item.count / pipelineTotal * 100 : 0
    return `${item.color} ${start}% ${pipelineCursor}%`
  }).join(', ')
  const today = new Date()
  const activityMonths = Array.from({ length: 12 }, (_, index) => {
    const date = new Date(today.getFullYear(), today.getMonth() - 11 + index, 1)
    return { key: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`, label: date.toLocaleDateString(undefined, { month: 'short' }) }
  })
  const counterpartRole = user.role === 'client' ? 'freelancer' : 'client'
  const teamActivity = new Map<string, { name: string; months: number[] }>()
  const getTeamMember = (name: string) => {
    const key = name.trim().toLocaleLowerCase()
    let member = teamActivity.get(key)
    if (!member) {
      member = { name: name.trim(), months: Array(12).fill(0) }
      teamActivity.set(key, member)
    }
    return member
  }
  for (const projectItem of projects) {
    const collaborator = (user.role === 'client' ? projectItem.freelancer_name : projectItem.client_name)?.trim()
    if (collaborator) getTeamMember(collaborator)
  }
  const projectById = new Map<string, Project>(projects.map((item) => [item.id, item] as const))
  const monthIndex = new Map(activityMonths.map((month, index) => [month.key, index] as const))
  for (const event of activity) {
    if (event.actor_type !== counterpartRole) continue
    const projectItem = projectById.get(event.project_id)
    if (!projectItem) continue
    const collaborator = (user.role === 'client' ? projectItem.freelancer_name : projectItem.client_name)?.trim()
    if (!collaborator) continue
    const date = new Date(event.created_at)
    const index = monthIndex.get(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`)
    if (index !== undefined) getTeamMember(collaborator).months[index] += 1
  }
  const teamRows = [...teamActivity.values()]
    .sort((left, right) => right.months.reduce((sum, count) => sum + count, 0) - left.months.reduce((sum, count) => sum + count, 0) || left.name.localeCompare(right.name))
  const visibleTeamRows = [
    ...teamRows.slice(0, 4).map((member) => ({ ...member, isSummary: false })),
    ...(teamRows.length ? [{ name: 'Team Activity', months: activityMonths.map((_, index) => teamRows.reduce((sum, member) => sum + member.months[index], 0)), isSummary: true }] : []),
  ]
  const activityLevel = (value: number) => value === 0 ? 0 : value <= 2 ? 1 : value <= 5 ? 2 : 3
  return <>
    <div className="dashboard-page-heading"><div><span className="eyebrow">YOUR WORKSPACE</span><h1>Collaboration Dashboard</h1><p>Projects, decisions, and payments in one shared workspace.</p></div><span className="dashboard-user-pill"><i/>{user.role === 'client' ? 'Client workspace' : 'Freelancer workspace'}</span></div>
    <div className="dashboard-section-title"><div><span className="eyebrow">WORKSPACE HEALTH</span><h2>Performance Hub</h2></div><p>Project pipeline and next steps at a glance.</p></div>
    <div className="dashboard-top-grid">
      <section className="surface performance-hub-card" aria-labelledby="pipeline-heading">
        <div className="section-head"><div><span className="eyebrow">PROJECT HEALTH</span><h2 id="pipeline-heading">Projects &amp; Pipeline</h2></div><span className="glance-project-count">{projects.length} total</span></div>
        <div className="performance-hub-content">
          <div className="pipeline-chart-area">
            <div className="pipeline-donut" role="img" aria-label={`Project pipeline: ${pipelineBuckets.map((item) => `${item.count} ${item.label.toLowerCase()}`).join(', ')}`} style={pipelineTotal ? { background: `conic-gradient(${pipelineGradient})` } : undefined}>
              <div className="pipeline-donut-center"><strong>{projects.length}</strong><span>projects</span></div>
            </div>
            <div className="pipeline-legend">{pipelineBuckets.map((item) => <div className="pipeline-legend-item" key={item.label}><i style={{ background: item.color }}/><span>{item.label}</span><strong>{item.count}</strong></div>)}</div>
          </div>
          <div className="performance-metrics">
            <div className="performance-metric"><span>Active projects</span><strong>{activeCount}</strong></div>
            <div className="performance-metric"><span>Pending invitations</span><strong>{invitationCount}</strong></div>
            <div className="performance-metric"><span>Awaiting decision</span><strong>{dueCount}</strong></div>
            <div className="performance-metric"><span>Milestones</span><strong>{milestoneCount}</strong></div>
            <div className="performance-overall-progress"><div><span>Overall progress</span><strong>{overallProgress}%</strong></div><div className="glance-progress" role="img" aria-label={`${overallProgress}% overall milestone progress`}><i style={{ width: `${overallProgress}%` }}/></div></div>
          </div>
        </div>
      </section>
      {user.role === 'client' ? <CreateProjectForm busy={busy} onCreate={onCreate}/> : <section className="surface create-card freelancer-invite-card"><div className="section-head"><div><span className="eyebrow">YOUR NEXT STEP</span><h2>Project invitations</h2></div><span className="create-card-icon" aria-hidden="true">✉</span></div><p>Review new project invitations, check the scope, and accept when you’re ready to get started.</p><button type="button" className="primary-button" onClick={() => { setProjectFilter('invited'); document.getElementById('projects-and-collaborations')?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }}>Review invitations <span>→</span></button></section>}
      <section className="surface collaboration-card"><div className="collaboration-card-heading"><div><span className="eyebrow">TRUSTFLOW WORKFLOW</span><h2>Start a collaboration</h2><p>Keep agreements, revisions, evidence, and payment decisions together from day one.</p></div><span className="create-card-icon collaboration-card-icon" aria-hidden="true">↗</span></div><button type="button" className="primary-button" onClick={onOpenResources}>Explore the workflow <span>→</span></button></section>
    </div>
    <section id="projects-and-collaborations" className="surface projects-panel">
      <div className="section-head project-section-heading"><div><h2>Your Projects &amp; Collaborations</h2></div><div className="project-filter-row"><div className="project-filter-tabs" role="tablist" aria-label="Filter projects"><button type="button" role="tab" aria-selected={projectFilter === 'all'} className={projectFilter === 'all' ? 'active' : ''} onClick={() => setProjectFilter('all')}>All Projects <span>{projects.length}</span></button><button type="button" role="tab" aria-selected={projectFilter === 'active'} className={projectFilter === 'active' ? 'active' : ''} onClick={() => setProjectFilter('active')}>Active <span>{activeCount}</span></button><button type="button" role="tab" aria-selected={projectFilter === 'invited'} className={projectFilter === 'invited' ? 'active' : ''} onClick={() => setProjectFilter('invited')}>Invitations <span>{invitationCount}</span></button></div><div className="project-table-controls">
        <div className="project-filter-menu-wrap"><button type="button" className={`project-control-button ${attentionOnly ? 'is-active' : ''}`} aria-expanded={filtersOpen} onClick={() => setFiltersOpen((open) => !open)}><span aria-hidden="true">☷</span> Filters{attentionOnly && <i>1</i>}</button>{filtersOpen && <div className="project-filter-popover" role="group" aria-label="Project filters"><label><input type="checkbox" checked={attentionOnly} onChange={(event) => setAttentionOnly(event.target.checked)}/> Needs attention only</label><small>{user.role === 'client' ? 'Includes invitations, reviews, and decisions due.' : 'Includes invitations and revision requests.'}</small></div>}</div>
        <label className="project-sort-control">Sort by<select aria-label="Sort projects" value={sortBy} onChange={(event) => setSortBy(event.target.value as 'recent' | 'name' | 'attention')}><option value="recent">Recently updated</option><option value="attention">Needs attention</option><option value="name">Project name</option></select></label>
      </div></div>
      </div>
      {projects.length === 0 ? <div className="projects-empty-new"><span className="empty-illustration"><i>◇</i><b>＋</b></span><h3>Your next collaboration starts here.</h3><p>{user.role === 'client' ? 'Create a project, set expectations, and invite a freelancer using their registered email.' : 'When a client invites you to a project, it will appear here with the agreed scope and next steps.'}</p>{user.role === 'client' && <button type="button" className="secondary-button" onClick={() => document.getElementById('create-project-form')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>Create your first project <span>→</span></button>}</div> : filteredProjects.length === 0 ? <div className="projects-empty-new compact"><span className="empty-illustration"><i>⌕</i></span><h3>No projects match these filters</h3><p>Clear the search or adjust the project filters to see your collaborations.</p><button type="button" className="text-button" onClick={() => { setProjectFilter('all'); setAttentionOnly(false); onClearSearch() }}>Clear filters</button></div> : <Suspense fallback={<div className="projects-grid-loading" role="status">Loading projects…</div>}><ProjectsGrid projects={filteredProjects} activity={activity} role={user.role} busy={busy} onOpen={onOpen} onEdit={onEditProject} onAccept={onAccept} onClearFilters={() => { setProjectFilter('all'); setAttentionOnly(false); onClearSearch() }}/></Suspense>}
    </section>
    <div className="dashboard-lower-grid">
      <RecentActivity activity={activity} loading={activityLoading} error={activityError} onOpenActivity={onOpenActivity} onViewAll={onOpenInsights}/>
      <section className="surface team-availability-card" aria-labelledby="team-availability-heading">
        <div className="section-head"><div><span className="eyebrow">MONTHLY ACTIVITY</span><h2 id="team-availability-heading">Team Activity</h2><p>Recent workspace updates by collaborator.</p></div><span className="team-member-count">{teamRows.length}</span></div>
        {visibleTeamRows.length === 0 ? <div className="team-availability-empty"><span>▦</span><strong>Your team map will appear here</strong><p>Collaborators show up as soon as a project is created or invited.</p></div> : <>
          <div className="team-heatmap" role="table" aria-label="Monthly project activity by collaborator">
            <div className="team-heatmap-row team-heatmap-header" role="row"><span role="columnheader">Collaborator</span>{activityMonths.map((month) => <span role="columnheader" key={month.key}>{month.label}</span>)}</div>
            {visibleTeamRows.map(({ name, months, isSummary }) => <div className={`team-heatmap-row${isSummary ? ' team-heatmap-summary' : ''}`} role="row" key={name}>
              <span className="team-heatmap-name" role="rowheader" title={name}><i>{isSummary ? 'Σ' : name.slice(0, 1).toUpperCase()}</i><span>{name}</span></span>
              {activityMonths.map((month, index) => {
                const value = months[index] || 0
                return <span className={`team-heat-cell level-${activityLevel(value)}`} role="cell" key={month.key} title={`${name} · ${month.label}: ${value} update${value === 1 ? '' : 's'}`} aria-label={`${month.label}: ${value} workflow update${value === 1 ? '' : 's'}`}/>
              })}
            </div>)}
          </div>
          <div className="team-heatmap-footer"><span>12-month view · latest 30 workspace events</span><div className="team-heatmap-legend"><span><i className="level-0"/>None</span><span><i className="level-1"/>Light</span><span><i className="level-2"/>Active</span><span><i className="level-3"/>Busy</span></div></div>
          <p className="team-availability-note">Activity is based on saved project events; calendar availability is not connected.</p>
        </>}
      </section>
    </div>
  </>
}

function SettingsPage({ user, busy, notificationPreferences, onPreferenceChange, onSave }: {
  user: User; busy: boolean; notificationPreferences: NotificationPreferences
  onPreferenceChange: (preferences: NotificationPreferences) => void
  onSave: (data: { name: string; current_password: string; new_password?: string }) => void
}) {
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
  return <>
    <div className="page-heading"><div><span className="eyebrow">ACCOUNT / PREFERENCES</span><h1>Account settings</h1><p>Manage your identity and password. Your account role is fixed after signup.</p></div><span className="settings-heading-mark">⚙</span></div>
    <div className="settings-layout">
      <section className="surface settings-card"><div className="section-head"><div><span className="eyebrow">PROFILE AND SECURITY</span><h2>Your account</h2><p>Keep your account details current and your credentials private.</p></div><span className="status-chip accepted">{user.role}</span></div><form className="stack-form" onSubmit={submit}><label>Name<input name="name" defaultValue={user.name} required maxLength={100}/><small>This name appears in your workspace and project collaboration views.</small></label><label>Email address<input value={user.email} readOnly/><small>{user.email_verified ? 'Your email address is confirmed.' : 'Your email address is not confirmed yet.'}</small></label><div className="settings-readonly-field"><span>ACCOUNT ROLE</span><strong>{user.role === 'client' ? 'Client' : 'Freelancer'}</strong><small>This is set when the account is created and cannot be changed here.</small></div><div className="settings-form-divider"><span>PASSWORD</span><i/></div><PasswordField label="Current password" name="current_password" autoComplete="current-password" required/><div className="settings-password-row"><PasswordField label="New password" name="new_password" autoComplete="new-password" minLength={12} hint="Leave blank to keep your current password."/><PasswordField label="Confirm new password" name="confirm_password" autoComplete="new-password" minLength={12}/></div>{passwordError && <p className="inline-error" role="alert">{passwordError}</p>}<button className="primary-button settings-save-button" disabled={busy}>{busy ? 'Saving…' : 'Save account changes'} <span>→</span></button></form><div className="settings-note"><strong>Forgot your password?</strong><p>Request a reset email from the sign-in page when email delivery is configured.</p><a href="/forgot-password">Open account recovery</a></div></section>
      <aside className="settings-side-stack">
        <section className="surface settings-identity-card"><div className="settings-cover-art"><span className="cover-orbit cover-orbit-a"/><span className="cover-orbit cover-orbit-b"/><span className="cover-monogram">{user.name.trim().slice(0, 1).toUpperCase()}</span><span className="cover-role-label">{user.role === 'client' ? 'CLIENT' : 'FREELANCER'}</span></div><div className="settings-identity-body"><span className="eyebrow">ACCOUNT IDENTITY</span><h2>{user.name}</h2><p>{user.email}</p><div className={`identity-verification ${user.email_verified ? 'verified' : 'pending'}`}><i/>{user.email_verified ? 'Email verified' : 'Email confirmation pending'}</div><div className="identity-facts"><div><span>ROLE</span><strong>{user.role === 'client' ? 'Client' : 'Freelancer'}</strong></div><div><span>WORKSPACE</span><strong>{user.role === 'client' ? 'Client studio' : 'Freelancer desk'}</strong></div></div></div></section>
        <section className="surface settings-security-card"><div className="settings-side-head"><span className="settings-side-icon green">✓</span><div><span className="eyebrow">SECURITY STATUS</span><h3>{user.email_verified ? 'Email confirmed' : 'One step left'}</h3></div></div><p>{user.email_verified ? 'Your account email is confirmed. Keep using a unique password and avoid sharing access.' : 'Confirm your email address to complete the account verification step.'}</p><div className="security-check-row"><span><i className={user.email_verified ? 'ok' : 'waiting'}/>Email confirmation</span><strong>{user.email_verified ? 'Complete' : 'Pending'}</strong></div><div className="security-check-row"><span><i className="ok"/>Authenticated session</span><strong>Active</strong></div><div className="security-check-row"><span><i className="ok"/>Password recovery</span><strong>Email link</strong></div></section>
        <NotificationPreferencesCard preferences={notificationPreferences} onChange={onPreferenceChange}/>
      </aside>
    </div>
  </>
}

function CreateProjectForm({ busy, onCreate }: { busy: boolean; onCreate: (data: { title: string; description: string; currency: string; freelancer_email: string }) => Promise<boolean> }) {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const succeeded = await onCreate({
      title: String(data.get('title')),
      description: String(data.get('description') || ''),
      currency: String(data.get('currency') || 'USD').trim().toUpperCase(),
      freelancer_email: String(data.get('freelancer_email')).trim(),
    })
    if (succeeded) form.reset()
  }

  return <section id="create-project-form" className="surface create-card"><div className="section-head"><div><span className="eyebrow">INVITE A FREELANCER</span><h2>Create New Project</h2></div><span className="create-card-icon" aria-hidden="true">＋</span></div><form className="stack-form compact-form create-project-compact" onSubmit={(event) => void submit(event)}><label>Project name<input name="title" required maxLength={160} placeholder="Website redesign"/></label><div className="create-project-invite-row"><label>Freelancer account email<input name="freelancer_email" type="email" required maxLength={254} placeholder="name@example.com"/></label><button className="primary-button" disabled={busy}>New Project <span>→</span></button></div><details className="create-project-details"><summary>Project details <span>Optional scope and currency</span></summary><div className="create-project-extra-fields"><label>Project description<textarea name="description" maxLength={5000} rows={2} placeholder="What are you building together?"/></label><label>Currency<input name="currency" defaultValue="USD" minLength={3} maxLength={3}/></label></div></details><small className="form-hint">The freelancer must already have a TrustFlow account to receive the invitation.</small></form></section>
}

function ProjectPage({ project, user, busy, onBack, onSelect, onCreateMilestone }: { project: Project; user: User; busy: boolean; onBack: () => void; onSelect: (id: string) => void; onCreateMilestone: (data: { title: string; acceptance_criteria: string[]; amount: string; currency: string; due_at?: string }) => Promise<boolean> }) {
  return <><button className="back-button" onClick={onBack}>← All projects</button><div className="page-heading project-title-heading"><div><span className="eyebrow">PROJECT · {project.membership_status.toUpperCase()}</span><h1>{project.title}</h1><p>{project.description || 'Milestones, evidence, and decisions for this collaboration.'}</p></div><div className="project-people"><span className="person-dot">{project.client_name?.slice(0,1)}</span><span>{project.client_name} <small>Client</small></span><span className="person-dot secondary-person">{project.freelancer_name?.slice(0,1)}</span><span>{project.freelancer_name} <small>Freelancer</small></span></div></div>
    <div className="project-layout"><section className="surface"><div className="section-head"><div><span className="eyebrow">AGREED WORK</span><h2>Milestones</h2></div><span className="subtle-count">{project.milestones?.length || 0} total</span></div>{project.membership_status === 'invited' && <div className="notice-box">The freelancer has not accepted the invitation. Milestone evidence is unavailable until they accept.</div>}{!project.milestones?.length ? <div className="empty-state"><span>◇</span><h3>No milestones added</h3><p>The client can define the deliverable, criteria, amount, and due date here.</p></div> : <div className="milestone-list">{project.milestones.map((item) => <button className="milestone-row" key={item.id} onClick={() => onSelect(item.id)}><span className="milestone-number">{item.title.slice(0,1).toUpperCase()}</span><span className="milestone-info"><strong>{item.title}</strong><small>{item.acceptance_criteria.length} criteria · revision {item.evidence_revision}</small></span><span className={`status-chip status-${item.status}`}>{item.status.replaceAll('_', ' ')}</span><span className="milestone-amount">{item.currency} {item.amount}</span><span className="row-arrow">→</span></button>)}</div>}</section>{user.role === 'client' && <CreateMilestoneForm project={project} busy={busy} onCreate={onCreateMilestone}/>}</div>
  </>
}

function CreateMilestoneForm({ project, busy, onCreate }: { project: Project; busy: boolean; onCreate: (data: { title: string; acceptance_criteria: string[]; amount: string; currency: string; due_at?: string }) => Promise<boolean> }) {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const dueValue = String(data.get('due_at') || '')
    const criteria = String(data.get('criteria') || '').split('\n').map((item) => item.trim()).filter(Boolean)
    const succeeded = await onCreate({
      title: String(data.get('title')),
      acceptance_criteria: criteria,
      amount: String(data.get('amount')),
      currency: String(data.get('currency')).trim().toUpperCase(),
      due_at: dueValue ? new Date(dueValue).toISOString() : undefined,
    })
    if (succeeded) form.reset()
  }

  return <section className="surface create-card"><div className="section-head"><div><span className="eyebrow">DEFINE THE AGREEMENT</span><h2>Add milestone</h2></div></div><form className="stack-form compact-form" onSubmit={(event) => void submit(event)}><label>Milestone name<input name="title" required maxLength={160} placeholder="Design handoff"/></label><label>Acceptance criteria<textarea name="criteria" required rows={5} placeholder={'One criterion per line\nFinal designs include mobile layouts\nSource files are included'} /></label><label>Agreed amount<input name="amount" type="number" step="0.01" min="0.01" required placeholder="500.00"/></label><label>Currency<input name="currency" defaultValue={project.currency} minLength={3} maxLength={3} required/></label><label>Deadline (optional)<input name="due_at" type="datetime-local"/></label><button className="primary-button" disabled={busy}>Add milestone <span>→</span></button></form></section>
}

function localDateTime(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

function EditMilestoneForm({ milestone, busy, onUpdate }: { milestone: Milestone; busy: boolean; onUpdate: (data: { title: string; acceptance_criteria: string[]; amount: string; currency: string; due_at?: string }) => Promise<boolean> }) {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const criteria = String(data.get('criteria')).split('\n').map((item) => item.trim()).filter(Boolean)
    const dueValue = String(data.get('due_at') || '')
    await onUpdate({ title: String(data.get('title')), acceptance_criteria: criteria, amount: String(data.get('amount')), currency: String(data.get('currency')).trim().toUpperCase(), due_at: dueValue ? new Date(dueValue).toISOString() : undefined })
  }
  return <details className="surface edit-milestone"><summary>Edit agreed terms</summary><p>Terms lock after evidence submission or payment begins.</p><form className="stack-form compact-form" onSubmit={submit}><label>Milestone name<input name="title" defaultValue={milestone.title} required maxLength={160}/></label><label>Acceptance criteria<textarea name="criteria" defaultValue={milestone.acceptance_criteria.join('\n')} rows={5} required/></label><label>Agreed amount<input name="amount" type="number" min="0.01" step="0.01" defaultValue={milestone.amount} required/></label><label>Currency<input name="currency" defaultValue={milestone.currency} minLength={3} maxLength={3} required/></label><label>Deadline<input name="due_at" type="datetime-local" defaultValue={localDateTime(milestone.due_at)}/></label><button className="primary-button" disabled={busy}>Save milestone terms <span>→</span></button></form></details>
}

function MilestonePage({ milestone, project, user, busy, audit, onBack, onRefresh, onUpdate, onEvidence, onAssess, onDecision, onOrder, onAuthorize, onCapture, onReconcile }: {
  milestone: Milestone; project: Project; user: User; busy: boolean; audit: Awaited<ReturnType<typeof getAudit>>
  onBack: () => void; onRefresh: () => void; onUpdate: (data: { title: string; acceptance_criteria: string[]; amount: string; currency: string; due_at?: string }) => Promise<boolean>; onEvidence: (text: string, links: string[], file?: File) => Promise<boolean>
  onAssess: () => void; onDecision: (decision: string, note: string) => void; onOrder: () => void
  onAuthorize: () => void; onCapture: () => void; onReconcile: () => void
}) {
  const report: AssessmentResponse | undefined = milestone.assessment_history?.[0]?.result_json
  const isClient = user.role === 'client'
  const revisionFeedback = (milestone.decisions || []).filter((decision) => decision.decision === 'revision_requested').slice(0, 5)
  async function evidenceSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const text = String(data.get('description') || '')
    const links = String(data.get('links') || '').split('\n').map((value) => value.trim()).filter(Boolean)
    const invalidLink = links.find((value) => { try { const url = new URL(value); return !['http:', 'https:'].includes(url.protocol) } catch { return true } })
    if (invalidLink) { window.alert(`Please enter a valid http(s) URL: ${invalidLink}`); return }
    const file = data.get('file')
    const succeeded = await onEvidence(text, links, file instanceof File && file.size ? file : undefined)
    if (succeeded) form.reset()
  }
  const latestReportCurrent = !!report && report.report?.evidence_revision === milestone.evidence_revision && !milestone.assessment_history?.[0]?.is_stale
  const currentReport = !!report?.assessment && latestReportCurrent
  return <><button className="back-button" onClick={onBack}>← {project.title}</button><div className="page-heading milestone-title-heading"><div><span className="eyebrow">MILESTONE · REVISION {milestone.evidence_revision}</span><h1>{milestone.title}</h1><p>{milestone.currency} {milestone.amount}{milestone.due_at ? ` · Due ${new Date(milestone.due_at).toLocaleDateString()}` : ''}</p></div><span className={`status-chip status-${milestone.status}`}>{milestone.status.replaceAll('_', ' ')}</span></div>
    <div className="milestone-work-grid"><div className="work-column"><section className="surface criteria-card"><div className="section-head"><div><span className="eyebrow">THE AGREEMENT</span><h2>Acceptance criteria</h2></div></div><ol className="criteria-list">{milestone.acceptance_criteria.map((item, index) => <li key={`${index}-${item}`}><span>{String(index + 1).padStart(2,'0')}</span>{item}</li>)}</ol></section>{user.role === 'client' && milestone.evidence_revision === 0 && !milestone.payment && <EditMilestoneForm milestone={milestone} busy={busy} onUpdate={onUpdate}/>}
      {user.role === 'freelancer' && <section className="surface"><div className="section-head"><div><span className="eyebrow">SUBMISSION</span><h2>Submit evidence</h2><p>Text, reference links, or a file. Links and files are stored but not opened or extracted by assessment.</p></div></div><form className="stack-form" onSubmit={evidenceSubmit}><label>What did you deliver?<textarea name="description" rows={5} maxLength={20000} placeholder="Add specific details and evidence excerpts…"/><small>Up to 20,000 characters. Any attachment is saved privately; its contents are not analyzed.</small></label><label>Reference links <textarea name="links" rows={2} placeholder="One http(s) URL per line"/></label><label>Attach a file<input name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.txt,.csv,application/pdf,image/png,image/jpeg,text/plain,text/csv"/><small>PDF, PNG, JPEG, TXT, or CSV · 3 MB maximum.</small></label><button className="primary-button" disabled={busy}>Submit evidence revision <span>→</span></button></form></section>}
      {!isClient && revisionFeedback.length > 0 && <section className="surface decision-card"><div className="section-head"><div><span className="eyebrow">CLIENT FEEDBACK</span><h2>Revision requests</h2><p>Feedback for this project, visible to its assigned freelancer.</p></div></div><div className="decision-history">{revisionFeedback.map((decision, index) => <article key={`${decision.decision}-${decision.created_at}-${index}`}><span>Revision requested · evidence revision {decision.evidence_revision}</span>{decision.note && <p>{decision.note}</p>}<small>{new Date(decision.created_at).toLocaleString()}</small></article>)}</div></section>}
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
  return <section className="surface payment-card"><div className="section-head"><div><span className="eyebrow">PAYMENT STATUS</span><h2>PayPal Sandbox</h2>
  <div className="paypal-partner">
    <img
      className="paypal-logo"
      src="/paypal-logo.svg"
      alt="PayPal"
    />
    <span>PAYMENT PARTNER</span>
  </div>
  </div><span className={`status-chip status-${payment?.status || 'not-created'}`}>{(payment?.status || 'not created').replaceAll('_', ' ')}</span></div><p>{payment ? `${payment.currency} ${payment.amount}` : 'Create a PayPal order for the agreed milestone amount.'}</p>{Number(payment?.refunded_amount || 0) > 0 && <small>Refunded: {payment?.currency} {payment?.refunded_amount}</small>}{payment?.paypal_order_id && <small>Order: {payment.paypal_order_id}</small>}{payment?.paypal_authorization_id && <small>Authorization: {payment.paypal_authorization_id}</small>}{payment?.paypal_capture_id && <small>Capture: {payment.paypal_capture_id}</small>}{payment?.status === 'created' && payment.paypal_approval_url && <a className="secondary-button link-button" href={payment.paypal_approval_url} target="_blank" rel="noreferrer">Continue to PayPal ↗</a>}{user.role === 'client' && !payment && <button className="secondary-button" disabled={busy || milestone.status === 'paid'} onClick={onOrder}>Create PayPal order</button>}{user.role === 'client' && payment?.status === 'created' && <button className="secondary-button" disabled={busy} onClick={onAuthorize}>Confirm buyer approval and authorize</button>}{user.role === 'client' && payment?.status === 'authorized' && milestone.status === 'approved' && <button className="primary-button" disabled={busy} onClick={onCapture}>Capture authorized amount <span>→</span></button>}{user.role === 'client' && payment?.status === 'capture_pending' && <button className="secondary-button" disabled={busy} onClick={onReconcile}>Reconcile with PayPal</button>}{payment?.status === 'captured' && <p className="payment-complete">Capture confirmed · {payment.paypal_capture_id}</p>}{(payment?.status === 'refunded' || payment?.status === 'partially_refunded') && <p className="payment-complete">PayPal confirmed {payment.status === 'refunded' ? 'the refund' : 'a partial refund'}.</p>}<small>TrustFlow coordinates this PayPal transaction; it does not provide legal escrow.</small></section>
}

export default App
