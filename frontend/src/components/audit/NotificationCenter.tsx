import type { Project, User } from '../../api/assessment'
import { buildNotifications, type NotificationPreferences, type WorkspaceNotification } from './notificationData'

export default function NotificationCenter({
  projects, role, preferences, open, readIds, onToggle, onMarkAllRead, onSelect,
}: {
  projects: Project[]; role: User['role']; preferences: NotificationPreferences; open: boolean; readIds: string[]
  onToggle: () => void; onMarkAllRead: () => void; onSelect: (item: WorkspaceNotification) => void
}) {
  const notifications = buildNotifications(projects, role, preferences)
  const unreadCount = notifications.filter((item) => !readIds.includes(item.id)).length
  return <div className="notification-wrap">
    <button type="button" className={`notification-trigger ${open ? 'is-open' : ''}`} aria-label={`Open notifications${unreadCount ? `, ${unreadCount} unread` : ''}`} aria-haspopup="dialog" aria-expanded={open} onClick={onToggle}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></svg>
      {unreadCount > 0 && <i className="notification-count">{unreadCount > 9 ? '9+' : unreadCount}</i>}
    </button>
    {open && <section className="notification-dropdown" role="dialog" aria-label="Notification centre">
      <div className="notification-head"><div><small>WORKSPACE INBOX</small><strong>Action items</strong></div><button type="button" disabled={!unreadCount} onClick={onMarkAllRead}>{unreadCount ? 'Mark all read' : 'All caught up'}</button></div>
      {notifications.length === 0 ? <div className="notification-empty"><span>✓</span><strong>You’re all caught up.</strong><p>New invitations, reviews, and payment updates will appear here.</p></div> : <div className="notification-list">
        {notifications.map((item) => {
          const isRead = readIds.includes(item.id)
          return <button type="button" className={`notification-item ${isRead ? 'is-read' : ''}`} key={item.id} onClick={() => onSelect(item)}>
            <span className={`notification-icon ${item.tone}`}>{item.icon}</span><span className="notification-copy"><strong>{item.title}</strong><span>{item.message}</span><small>{item.detail}</small></span>{!isRead && <i className="notification-unread-dot" aria-label="Unread"/>}
          </button>
        })}
      </div>}
    </section>}
  </div>
}
