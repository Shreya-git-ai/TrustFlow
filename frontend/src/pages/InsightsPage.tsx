import type { Project, User, WorkspaceActivity } from '../api/assessment'

const activityLabels: Record<string, string> = {
  'project.created': 'Project created',
  'project.invitation_accepted': 'Invitation accepted',
  'milestone.created': 'Milestone added',
  'milestone.updated': 'Milestone updated',
  'evidence.submitted': 'Evidence submitted',
  'assessment.completed': 'Assessment completed',
  'assessment.failed': 'Assessment needs attention',
  'milestone.approved': 'Milestone approved',
  'milestone.revision_requested': 'Revision requested',
  'milestone.revoked': 'Approval revoked',
  'payment.initiated': 'Payment started',
  'payment.authorized': 'Payment authorized',
  'payment.captured': 'Payment captured',
}

export default function InsightsPage({
  projects, role, activity, loading, error, onRefresh, onOpenProject, onOpenActivity,
}: {
  projects: Project[]; role: User['role']; activity: WorkspaceActivity[]
  loading: boolean; error: string; onRefresh: () => void; onOpenProject: (id: string) => void
  onOpenActivity: (item: WorkspaceActivity) => void
}) {
  const accepted = projects.filter((project) => project.membership_status === 'accepted').length
  const invited = projects.filter((project) => project.membership_status === 'invited').length
  const milestones = projects.reduce((sum, project) => sum + (project.milestone_count || 0), 0)
  const reviews = projects.reduce((sum, project) => sum + (role === 'client' ? project.submitted_count || 0 : project.revision_count || 0), 0)
  const decisions = projects.reduce((sum, project) => sum + (project.decision_due_count || 0), 0)
  const payments = projects.reduce((sum, project) => sum + (project.active_payment_count || 0), 0)
  const activityError = error || ''
  const projectById = new Map<string, Project>(projects.map((project) => [project.id, project] as const))
  const auditProjects = new Map<string, { id: string; title: string; loose: WorkspaceActivity[]; milestones: Map<string, { title: string; events: WorkspaceActivity[] }> }>()
  for (const item of activity) {
    let group = auditProjects.get(item.project_id)
    if (!group) {
      group = { id: item.project_id, title: item.project_title, loose: [], milestones: new Map() }
      auditProjects.set(item.project_id, group)
    }
    if (!item.milestone_id) {
      group.loose.push(item)
      continue
    }
    let milestone = group.milestones.get(item.milestone_id)
    if (!milestone) {
      milestone = { title: item.milestone_title || 'Milestone', events: [] }
      group.milestones.set(item.milestone_id, milestone)
    }
    milestone.events.push(item)
  }
  return <>
    <div className="page-heading workspace-page-heading"><div><span className="eyebrow">WORKSPACE / INSIGHTS</span><h1>Insights</h1><p>A live view of your projects, reviews, decisions, and payment progress.</p></div><button type="button" className="secondary-button" onClick={onRefresh} disabled={loading}>↻ Refresh activity</button></div>
    <div className="insights-kpi-grid">
      <article className="surface insights-kpi"><span className="insights-kpi-icon purple">▦</span><div><small>PROJECTS</small><strong>{projects.length}</strong><span>{accepted} active · {invited} invited</span></div></article>
      <article className="surface insights-kpi"><span className="insights-kpi-icon blue">◇</span><div><small>MILESTONES</small><strong>{milestones}</strong><span>Across your current projects</span></div></article>
      <article className="surface insights-kpi"><span className="insights-kpi-icon amber">◎</span><div><small>{role === 'client' ? 'SUBMISSIONS' : 'REVISION REQUESTS'}</small><strong>{reviews}</strong><span>{role === 'client' ? 'Submitted evidence to review' : 'Milestones needing another pass'}</span></div></article>
      <article className="surface insights-kpi"><span className="insights-kpi-icon green">✓</span><div><small>DECISIONS DUE</small><strong>{decisions}</strong><span>Current successful assessments awaiting a client decision</span></div></article>
    </div>
    <div className="insights-layout">
      <section className="surface insights-projects"><div className="section-head"><div><span className="eyebrow">PROJECT MIX</span><h2>Workspace status</h2><p>{payments} active payment{payments === 1 ? '' : 's'} across these projects.</p></div></div>
        <div className="insights-project-bar" role="img" aria-label={`${accepted} active projects and ${invited} pending invitations`}><span style={{ width: `${projects.length ? accepted / projects.length * 100 : 0}%` }}/><span style={{ width: `${projects.length ? invited / projects.length * 100 : 0}%` }}/></div>
        <div className="insights-legend"><span><i className="legend-active"/>Active projects <strong>{accepted}</strong></span><span><i className="legend-invited"/>Invitations <strong>{invited}</strong></span></div>
        <div className="insights-project-list">{projects.slice(0, 8).map((project) => <button type="button" key={project.id} onClick={() => onOpenProject(project.id)}><span><strong>{project.title}</strong><small>{role === 'client' ? project.freelancer_name : project.client_name}</small></span><span className={`status-chip ${project.membership_status}`}>{project.membership_status === 'invited' ? 'Invited' : project.membership_status === 'declined' ? 'Declined' : 'Active'}</span><i aria-hidden="true">↗</i></button>)}</div>
        {projects.length === 0 && <p className="muted">Create or accept a project to start seeing workspace insights.</p>}
      </section>
      <section className="surface insights-activity"><div className="section-head"><div><span className="eyebrow">AUDIT EVENTS</span><h2>Recent changes</h2><p>Events recorded from project workflows, grouped by project and milestone.</p></div></div>
        {loading ? <div className="activity-state" role="status">Loading activity…</div> : activityError ? <div className="activity-state error" role="alert">{activityError}</div> : activity.length === 0 ? <div className="activity-state">No project events yet.</div> : <div className="audit-tree">
          {[...auditProjects.values()].map((group) => {
            const project = projectById.get(group.id)
            const isActive = project?.membership_status === 'accepted'
            return <section className="audit-project" key={group.id}>
              <button type="button" className="audit-project-row" onClick={() => onOpenProject(group.id)}>
                <span className="audit-project-icon" aria-hidden="true">▣</span><strong>{group.title}</strong>
                <span className={`audit-project-status ${isActive ? 'active' : project?.membership_status || 'active'}`}><i/>{isActive ? 'Active' : project?.membership_status === 'invited' ? 'Invitation' : project?.membership_status === 'declined' ? 'Declined' : 'Activity'}</span>
                <i className="audit-branch-arrow" aria-hidden="true">↗</i>
              </button>
              <div className="audit-project-branches">
                {group.loose.map((item) => <button type="button" className="audit-event-row project-event" key={`${item.event_type}-${item.created_at}`} onClick={() => onOpenActivity(item)}>
                  <span className={`audit-event-marker ${item.event_type.split('.')[0]}`} aria-hidden="true"/><span className="audit-event-copy"><strong>{activityLabels[item.event_type] || item.event_type.replaceAll('.', ' ')}</strong><small>{new Date(item.created_at).toLocaleString()} · {item.actor_type}</small></span><i className="audit-branch-arrow" aria-hidden="true">↗</i>
                </button>)}
                {[...group.milestones.entries()].map(([milestoneId, milestone]) => <div className="audit-milestone" key={milestoneId}>
                  <div className="audit-milestone-row"><span className="audit-milestone-node" aria-hidden="true"/><span className="audit-milestone-icon" aria-hidden="true">◇</span><strong>{milestone.title}</strong></div>
                  <div className="audit-milestone-events">{milestone.events.map((item) => <button type="button" className="audit-event-row" key={`${item.event_type}-${item.created_at}`} onClick={() => onOpenActivity(item)}>
                    <span className={`audit-event-marker ${item.event_type.split('.')[0]}`} aria-hidden="true"/><span className="audit-event-copy"><strong>{activityLabels[item.event_type] || item.event_type.replaceAll('.', ' ')}</strong><small>{new Date(item.created_at).toLocaleString()} · {item.actor_type}</small></span><i className="audit-branch-arrow" aria-hidden="true">↗</i>
                  </button>)}</div>
                </div>)}
              </div>
            </section>
          })}
        </div>}
      </section>
    </div>
  </>
}
