import type { Project, User } from '../../api/assessment'

export type WorkspaceNotification = {
  id: string
  title: string
  message: string
  detail: string
  icon: string
  tone: 'purple' | 'green' | 'amber'
  projectId?: string
  destination: 'project' | 'payments'
}

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
  } catch { /* use defaults if this browser cannot read saved preferences */ }
  return defaultNotificationPreferences
}

export function buildNotifications(projects: Project[], role: User['role'], preferences = defaultNotificationPreferences): WorkspaceNotification[] {
  const notifications: WorkspaceNotification[] = []
  for (const project of projects) {
    const submissionCount = role === 'client' ? project.submitted_count || 0 : project.revision_count || 0
    if (preferences.projectUpdates && project.membership_status === 'invited' && role === 'freelancer') {
      notifications.push({
        id: `invitation:${project.id}`,
        title: 'Project invitation',
        message: project.title,
        detail: 'Review the scope and accept the invitation to begin.',
        icon: '↗', tone: 'amber', projectId: project.id, destination: 'project',
      })
    }
    if (preferences.projectUpdates && submissionCount > 0) {
      notifications.push({
        id: `${role === 'client' ? 'submission' : 'revision'}:${project.id}:${submissionCount}`,
        title: role === 'client' ? 'Evidence ready to review' : 'Revision requested',
        message: project.title,
        detail: `${submissionCount} milestone${submissionCount === 1 ? '' : 's'} ${role === 'client' ? 'submitted for review' : 'need another revision'}.`,
        icon: role === 'client' ? '◇' : '↻', tone: 'purple', projectId: project.id, destination: 'project',
      })
    }
    if (preferences.projectUpdates && role === 'client' && (project.decision_due_count || 0) > 0) {
      const count = project.decision_due_count || 0
      notifications.push({
        id: `decision:${project.id}:${count}`,
        title: 'Decision needed',
        message: project.title,
        detail: `${count} assessed milestone${count === 1 ? '' : 's'} await your decision.`,
        icon: '✓', tone: 'green', projectId: project.id, destination: 'project',
      })
    }
    if (preferences.paymentAlerts && (project.active_payment_count || 0) > 0) {
      const count = project.active_payment_count || 0
      notifications.push({
        id: `payment:${project.id}:${count}`,
        title: 'Payment in progress',
        message: project.title,
        detail: `${count} payment${count === 1 ? '' : 's'} need tracking in PayPal.`,
        icon: '$', tone: 'amber', projectId: project.id, destination: 'payments',
      })
    }
  }
  return notifications
}
