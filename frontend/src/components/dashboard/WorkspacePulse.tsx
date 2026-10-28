import type { Project, User } from '../../api/assessment'

export default function WorkspacePulse({
  user, projects, projectFilter, onFilter, onPayments,
}: {
  user: User; projects: Project[]; projectFilter: 'all' | 'active' | 'invited'
  onFilter: (filter: 'all' | 'active' | 'invited') => void; onPayments: () => void
}) {
  const activeCount = projects.filter((project) => project.membership_status === 'accepted').length
  const invitationCount = projects.filter((project) => project.membership_status === 'invited').length
  const milestoneCount = projects.reduce((sum, project) => sum + (project.milestone_count || 0), 0)
  const reviewCount = projects.reduce((sum, project) => sum + (user.role === 'client' ? project.decision_due_count || 0 : project.revision_count || 0), 0)
  const paymentCount = projects.reduce((sum, project) => sum + (project.active_payment_count || 0), 0)

  return <section className="surface workspace-pulse-card">
    <div className="section-head"><div><span className="eyebrow">AT A GLANCE</span><h2>Workspace pulse</h2></div><span className="pulse-icon" aria-hidden="true">◌</span></div>
    <div className="pulse-total"><strong>{projects.length}</strong><span>projects in your workspace</span></div>
    <div className="pulse-bar" role="img" aria-label={`${activeCount} active projects, ${invitationCount} pending invitations`}><span style={{ width: `${projects.length ? activeCount / projects.length * 100 : 0}%` }}/><span style={{ width: `${projects.length ? invitationCount / projects.length * 100 : 0}%` }}/></div>
    <div className="pulse-legend">
      <button type="button" className={projectFilter === 'active' ? 'selected' : ''} onClick={() => onFilter(projectFilter === 'active' ? 'all' : 'active')}><i className="legend-active"/>Active <strong>{activeCount}</strong></button>
      <button type="button" className={projectFilter === 'invited' ? 'selected' : ''} onClick={() => onFilter(projectFilter === 'invited' ? 'all' : 'invited')}><i className="legend-invited"/>Invitations <strong>{invitationCount}</strong></button>
    </div>
    <div className="pulse-divider"/>
    <div className="pulse-metric-row"><span>Milestones across projects</span><strong>{milestoneCount}</strong></div>
    <div className="pulse-metric-row"><span>{user.role === 'client' ? 'Awaiting your decision' : 'Revision requests'}</span><strong>{reviewCount}</strong></div>
    <button type="button" className="pulse-metric-row pulse-payment-link" onClick={onPayments}><span>Payments in progress</span><strong>{paymentCount}<i aria-hidden="true">↗</i></strong></button>
    <p className="pulse-footnote">Counts update from your current project records.</p>
  </section>
}
