import type { WorkspacePayment } from '../../api/assessment'

function statusLabel(status: string) {
  return status.replaceAll('_', ' ')
}

export default function PaymentsPage({
  payments, loading, error, onRefresh, onOpenMilestone, onOverview,
}: {
  payments: WorkspacePayment[]; loading: boolean; error: string
  onRefresh: () => void; onOpenMilestone: (payment: WorkspacePayment) => void; onOverview: () => void
}) {
  const needsAction = payments.filter((payment) => ['created', 'buyer_approved', 'authorized', 'capture_pending'].includes(payment.status)).length
  const captured = payments.filter((payment) => payment.status === 'captured').length
  return <>
    <div className="page-heading workspace-page-heading"><div><span className="eyebrow">WORKSPACE / PAYMENTS</span><h1>Payments</h1><p>Track PayPal payment records linked to your project milestones.</p></div><button type="button" className="secondary-button" onClick={onRefresh} disabled={loading}>↻ Refresh</button></div>
    <div className="workspace-summary-row"><div className="surface workspace-summary-card"><small>PAYMENT RECORDS</small><strong>{payments.length}</strong><span>Created for project milestones</span></div><div className="surface workspace-summary-card"><small>IN PROGRESS</small><strong>{needsAction}</strong><span>Awaiting the next payment step</span></div><div className="surface workspace-summary-card"><small>CAPTURED</small><strong>{captured}</strong><span>Confirmed by PayPal</span></div></div>
    <section className="surface workspace-data-card"><div className="section-head"><div><span className="eyebrow">PAYMENT LEDGER</span><h2>Milestone payments</h2></div><span className="subtle-count">{payments.length} records</span></div>
      {loading ? <div className="workspace-empty" role="status">Loading payment records…</div> : error ? <div className="workspace-empty error" role="alert">{error}<button className="text-button" type="button" onClick={onRefresh}>Try again</button></div> : payments.length === 0 ? <div className="workspace-empty"><span className="empty-illustration"><i>$</i></span><h3>No payment records yet</h3><p>Payment records appear after a client creates a PayPal order for an agreed milestone.</p><button type="button" className="secondary-button" onClick={onOverview}>View projects <span>→</span></button></div> : <div className="payment-ledger-wrap"><table className="payment-ledger"><thead><tr><th>Project / milestone</th><th>Amount</th><th>Status</th><th>Last updated</th><th><span className="sr-only">Action</span></th></tr></thead><tbody>
        {payments.map((payment) => <tr key={payment.id}><td><strong>{payment.project_title}</strong><span>{payment.milestone_title}</span></td><td className="ledger-amount">{payment.currency} {payment.amount}</td><td><span className={`status-chip status-${payment.status}`}>{statusLabel(payment.status)}</span></td><td>{new Date(payment.updated_at).toLocaleString()}</td><td><button type="button" className="text-button" onClick={() => onOpenMilestone(payment)}>Open milestone →</button></td></tr>)}
      </tbody></table></div>}
      <p className="payment-ledger-note">TrustFlow coordinates PayPal transactions; it does not provide legal escrow. Payment operations remain available from each milestone.</p>
    </section>
  </>
}
