import type { WorkspaceActivity } from '../../api/assessment'

const eventLabels: Record<string, string> = {
  'project.created': 'Project created',
  'project.invitation_accepted': 'Invitation accepted',
  'milestone.created': 'Milestone added',
  'milestone.updated': 'Milestone terms updated',
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

function eventTone(eventType: string) {
  if (eventType.startsWith('payment.')) return 'green'
  if (eventType.includes('assessment') || eventType.includes('decision') || eventType.includes('approved')) return 'amber'
  return 'purple'
}

export default function RecentActivity({
  activity, loading, error, onOpenActivity, onViewAll,
}: {
  activity: WorkspaceActivity[]; loading: boolean; error: string
  onOpenActivity: (item: WorkspaceActivity) => void; onViewAll: () => void
}) {
  return <section className="surface activity-preview-card">
    <div className="section-head"><div><span className="eyebrow">WORKSPACE UPDATES</span><h2>Project Activity Timeline</h2><p>Updates recorded across your projects.</p></div><button className="text-button activity-view-all" type="button" onClick={onViewAll}>View insights →</button></div>
    {loading ? <div className="activity-state" role="status">Loading project activity…</div> : error ? <div className="activity-state error" role="alert">{error}</div> : activity.length === 0 ? <div className="activity-state"><strong>No activity yet</strong><p>Project creation, submissions, decisions, and payment updates will appear here.</p></div> : <div className="activity-preview-list">
      {activity.slice(0, 5).map((item) => <button className="activity-event" type="button" key={`${item.event_type}-${item.created_at}-${item.project_id}`} onClick={() => onOpenActivity(item)}>
        <span className={`activity-preview-icon ${eventTone(item.event_type)}`}>{item.event_type.startsWith('payment.') ? '$' : item.event_type.startsWith('evidence.') ? '◇' : item.event_type.includes('approved') ? '✓' : '↗'}</span>
        <span className="activity-event-copy"><strong>{eventLabels[item.event_type] || item.event_type.replaceAll('.', ' ')}</strong><span>{item.project_title}{item.milestone_title ? ` · ${item.milestone_title}` : ''}</span><small>{new Date(item.created_at).toLocaleString()} · {item.actor_type}</small></span>
        <span className="activity-event-arrow" aria-hidden="true">↗</span>
      </button>)}
    </div>}
  </section>
}
