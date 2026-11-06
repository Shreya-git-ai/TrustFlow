import type { NotificationPreferences } from './notificationData'

export default function NotificationPreferencesCard({
  preferences, onChange,
}: { preferences: NotificationPreferences; onChange: (preferences: NotificationPreferences) => void }) {
  return <section className="surface settings-preferences-card">
    <div className="settings-side-head"><span className="settings-side-icon purple">☷</span><div><span className="eyebrow">PREFERENCES</span><h3>Notifications</h3></div></div>
    <p>Choose which workspace alerts appear in your notification centre. These preferences are saved to your account across browsers.</p>
    <label className="preference-toggle-row"><span><strong>Project updates</strong><small>Invitations, evidence, revisions, and decisions</small></span><input type="checkbox" checked={preferences.projectUpdates} onChange={(event) => onChange({ ...preferences, projectUpdates: event.target.checked })}/></label>
    <label className="preference-toggle-row"><span><strong>Payment alerts</strong><small>Milestone payments in progress</small></span><input type="checkbox" checked={preferences.paymentAlerts} onChange={(event) => onChange({ ...preferences, paymentAlerts: event.target.checked })}/></label>
  </section>
}
