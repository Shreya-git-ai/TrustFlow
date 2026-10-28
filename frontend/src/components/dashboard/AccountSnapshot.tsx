import type { User } from '../../api/assessment'

export default function AccountSnapshot({ user, projectCount, onSettings }: { user: User; projectCount: number; onSettings: () => void }) {
  return <section className="surface account-snapshot-card">
    <div className="section-head"><div><span className="eyebrow">ACCOUNT SNAPSHOT</span><h2>Your workspace details</h2><p>Current account and verification status.</p></div><button type="button" className="snapshot-edit" onClick={onSettings} aria-label="Open account settings">↗</button></div>
    <div className="snapshot-profile"><span className="snapshot-avatar">{user.name.trim().slice(0, 1).toUpperCase()}</span><div><strong>{user.name}</strong><span>{user.email}</span></div><span className={`snapshot-verification ${user.email_verified ? 'verified' : 'pending'}`}><i/>{user.email_verified ? 'Verified' : 'Pending'}</span></div>
    <div className="snapshot-details"><div><span>ACCOUNT ROLE</span><strong>{user.role === 'client' ? 'Client' : 'Freelancer'}</strong></div><div><span>WORKSPACE</span><strong>{user.role === 'client' ? 'Client studio' : 'Freelancer desk'}</strong></div><div><span>PROJECTS</span><strong>{projectCount} total</strong></div><div><span>SECURITY</span><strong>{user.email_verified ? 'Email confirmed' : 'Verification needed'}</strong></div></div>
    <button type="button" className="secondary-button snapshot-settings-button" onClick={onSettings}>Manage account settings <span>→</span></button>
  </section>
}
