import type { WorkspaceNotification } from '../../api/assessment'

export type NotificationPreferences = { projectUpdates: boolean; paymentAlerts: boolean }

export const defaultNotificationPreferences: NotificationPreferences = { projectUpdates: true, paymentAlerts: true }

export function savedNotificationPreferences(userId: string): NotificationPreferences {
  try {
    const saved = JSON.parse(window.localStorage.getItem(`trustflow.notifications.preferences.${userId}`) || 'null')
    if (saved && typeof saved === 'object') {
      return {
        projectUpdates: typeof saved.projectUpdates === 'boolean' ? saved.projectUpdates : true,
        paymentAlerts: typeof saved.paymentAlerts === 'boolean' ? saved.paymentAlerts : true,
      }
    }
  } catch { /* use defaults when browser storage is unavailable */ }
  return defaultNotificationPreferences
}

export function notificationsForPreferences(items: WorkspaceNotification[], preferences: NotificationPreferences) {
  return items.filter((item) => item.event_type.startsWith('payment.') ? preferences.paymentAlerts : preferences.projectUpdates)
}

const eventTitles: Record<string, string> = {
  'project.created': 'Project invitation',
  'project.invitation_accepted': 'Invitation accepted',
  'project.invitation_declined': 'Invitation declined',
  'project.invitation_cancelled': 'Invitation cancelled',
  'project.invitation_resent': 'Invitation resent',
  'milestone.created': 'Milestone terms proposed',
  'milestone.updated': 'Milestone terms updated',
  'milestone.agreement_accepted': 'Milestone terms accepted',
  'milestone.agreement_changes_requested': 'Milestone changes requested',
  'evidence.submitted': 'Evidence ready to review',
  'assessment.completed': 'Assessment completed',
  'assessment.failed': 'Assessment needs attention',
  'milestone.approved': 'Milestone approved',
  'milestone.revision_requested': 'Revision requested',
  'milestone.revoked': 'Approval revoked',
  'payment.initiated': 'Payment started',
  'payment.authorized': 'Payment authorized',
  'payment.captured': 'Payment captured',
  'refund.proposed': 'Refund proposal received',
  'refund.approved': 'Refund approved',
  'refund.rejected': 'Refund rejected',
  'refund.completed': 'Refund completed',
}

export function notificationTitle(item: WorkspaceNotification) {
  return eventTitles[item.event_type] || item.event_type.replaceAll('.', ' ')
}

export function notificationDetail(item: WorkspaceNotification) {
  const parts = [item.project_title, item.milestone_title].filter(Boolean)
  return parts.join(' · ') || 'Workspace update'
}

export function notificationDestination(item: WorkspaceNotification): 'project' | 'payments' {
  return item.event_type.startsWith('payment.') || item.event_type.startsWith('refund.') ? 'payments' : 'project'
}

export function notificationTone(item: WorkspaceNotification): 'purple' | 'green' | 'amber' {
  if (item.event_type.startsWith('payment.') || item.event_type.startsWith('refund.')) return 'green'
  if (item.event_type.includes('assessment') || item.event_type.includes('approved') || item.event_type.includes('decision')) return 'amber'
  return 'purple'
}

export function notificationIcon(item: WorkspaceNotification) {
  if (item.event_type.startsWith('payment.') || item.event_type.startsWith('refund.')) return '$'
  if (item.event_type.startsWith('evidence.')) return '◇'
  if (item.event_type.includes('approved') || item.event_type.includes('accepted')) return '✓'
  return '↗'
}
