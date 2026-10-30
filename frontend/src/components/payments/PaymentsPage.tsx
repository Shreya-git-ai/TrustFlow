import { lazy, Suspense } from 'react'
import type { RefundProposal, User, WorkspacePayment } from '../../api/assessment'

const RefundProposalsGrid = lazy(() => import('./RefundProposalsGrid'))

function statusLabel(status: string) {
  return status.replaceAll('_', ' ')
}

export default function PaymentsPage({
  payments,
  paymentsLoading,
  paymentsError,
  proposals,
  proposalsLoading,
  proposalsError,
  role,
  busy,
  onRefresh,
  onOpenMilestone,
  onOverview,
  onRefundApprove,
  onRefundReject,
}: {
  payments: WorkspacePayment[]
  paymentsLoading: boolean
  paymentsError: string
  proposals: RefundProposal[]
  proposalsLoading: boolean
  proposalsError: string
  role: User['role']
  busy: boolean
  onRefresh: () => void
  onOpenMilestone: (payment: WorkspacePayment) => void
  onOverview: () => void
  onRefundApprove: (proposal: RefundProposal) => void
  onRefundReject: (proposal: RefundProposal) => void
}) {
  const needsAction = payments.filter((payment) => ['created', 'buyer_approved', 'authorized', 'capture_pending'].includes(payment.status)).length
  const captured = payments.filter((payment) => ['captured', 'partially_refunded', 'refunded'].includes(payment.status)).length

  return <>
    <div className="page-heading workspace-page-heading">
      <div>
        <span className="eyebrow">WORKSPACE / PAYMENTS</span>
        <h1>Payments</h1>
        <p>Track PayPal payments linked to your project milestones.</p>
      </div>
      <button type="button" className="secondary-button" onClick={onRefresh} disabled={paymentsLoading || proposalsLoading}>↻ Refresh</button>
    </div>
    <div className="workspace-summary-row">
      <div className="surface workspace-summary-card"><small>PAYMENT RECORDS</small><strong>{payments.length}</strong><span>Created for project milestones</span></div>
      <div className="surface workspace-summary-card"><small>IN PROGRESS</small><strong>{needsAction}</strong><span>Awaiting the next payment step</span></div>
      <div className="surface workspace-summary-card"><small>CAPTURED</small><strong>{captured}</strong><span>Including completed refunds</span></div>
    </div>
    <section className="surface workspace-data-card">
      <div className="section-head">
        <div><span className="eyebrow">PAYMENT LEDGER</span><h2>Milestone payments</h2></div>
        <span className="subtle-count">{payments.length} records</span>
      </div>
      {paymentsLoading ? <div className="workspace-empty" role="status">Loading payment records…</div>
        : paymentsError ? <div className="workspace-empty error" role="alert">{paymentsError}<button className="text-button" type="button" onClick={onRefresh}>Try again</button></div>
          : payments.length === 0 ? <div className="workspace-empty">
            <span className="empty-illustration"><i>$</i></span><h3>No payment records yet</h3>
            <p>Payment records appear after a client creates a PayPal order for an agreed milestone.</p>
            <button type="button" className="secondary-button" onClick={onOverview}>View projects <span>→</span></button>
          </div> : <div className="payment-ledger-wrap"><table className="payment-ledger">
            <thead><tr><th>Project / milestone</th><th>Amount</th><th>Refunded</th><th>Status</th><th>Last updated</th><th><span className="sr-only">Action</span></th></tr></thead>
            <tbody>{payments.map((payment) => <tr key={payment.id}>
              <td><strong>{payment.project_title}</strong><span>{payment.milestone_title}</span></td>
              <td className="ledger-amount">{payment.currency} {payment.amount}</td>
              <td className="ledger-amount">{payment.currency} {payment.refunded_amount || '0.00'}</td>
              <td><span className={`status-chip status-${payment.status}`}>{statusLabel(payment.status)}</span></td>
              <td>{new Date(payment.updated_at).toLocaleString()}</td>
              <td><button type="button" className="text-button" onClick={() => onOpenMilestone(payment)}>Open milestone →</button></td>
            </tr>)}</tbody>
          </table></div>}
      <p className="payment-ledger-note">TrustFlow coordinates PayPal transactions; it does not provide legal escrow. Payment operations remain available from each milestone.</p>
    </section>
    {role === 'client' && <Suspense fallback={<section className="surface refund-review-section" role="status">Loading refund review…</section>}>
      <RefundProposalsGrid
        proposals={proposals}
        loading={proposalsLoading}
        error={proposalsError}
        busy={busy}
        onApprove={onRefundApprove}
        onReject={onRefundReject}
        onRefresh={onRefresh}
      />
    </Suspense>}
  </>
}
