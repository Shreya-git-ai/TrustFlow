import type { WorkspaceNotification } from '../../api/assessment'
import {
  notificationDetail, notificationDestination, notificationIcon, notificationTitle,
  notificationTone, notificationsForPreferences, type NotificationPreferences,
} from './notificationData'

export default function NotificationCenter({
  notifications, preferences, open, onToggle, onMarkAllRead, onSelect,
}: {
  notifications: WorkspaceNotification[]; preferences: NotificationPreferences; open: boolean
  onToggle: () => void; onMarkAllRead: (eventIds: number[]) => void; onSelect: (item: WorkspaceNotification) => void
}) {
  const visible = notificationsForPreferences(notifications, preferences)
  const unreadCount = visible.filter((item) => !item.is_read).length
  return <div className="notification-wrap">
    <button type="button" className={`notification-trigger ${open ? 'is-open' : ''}`} aria-label={`Open notifications${unreadCount ? `, ${unreadCount} unread` : ''}`} aria-haspopup="dialog" aria-expanded={open} onClick={onToggle}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></svg>
      {unreadCount > 0 && <i className="notification-count">{unreadCount > 9 ? '9+' : unreadCount}</i>}
    </button>
    {open && <section className="notification-dropdown" role="dialog" aria-label="Notification centre">
      <div className="notification-head"><div><small>WORKSPACE INBOX</small><strong>Recent updates</strong></div><button type="button" disabled={!unreadCount} onClick={() => onMarkAllRead(visible.filter((item) => !item.is_read).map((item) => item.event_id))}>{unreadCount ? 'Mark all read' : 'All caught up'}</button></div>
      {visible.length === 0 ? <div className="notification-empty"><span>✓</span><strong>You’re all caught up.</strong><p>New project and payment activity will appear here.</p></div> : <div className="notification-list">
        {visible.map((item) => <button type="button" className={`notification-item ${item.is_read ? 'is-read' : ''}`} key={item.event_id} onClick={() => onSelect(item)}>
          <span className={`notification-icon ${notificationTone(item)}`}>{notificationIcon(item)}</span><span className="notification-copy"><strong>{notificationTitle(item)}</strong><span>{notificationDetail(item)}</span><small>{new Date(item.created_at).toLocaleString()} · {item.actor_type}</small></span>{!item.is_read && <i className="notification-unread-dot" aria-label="Unread"/>}
        </button>)}
      </div>}
    </section>}
  </div>
}
