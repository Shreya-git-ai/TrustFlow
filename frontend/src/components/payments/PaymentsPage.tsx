import { lazy, Suspense, useMemo, useState } from 'react'
import type { RefundProposal, User, WorkspacePayment } from '../../api/assessment'

const RefundProposalsGrid = lazy(() => import('./RefundProposalsGrid'))
type PaymentFilter = 'all' | 'in_progress' | 'captured' | 'attention'
const activeStatuses = ['created', 'buyer_approved', 'authorized', 'capture_pending']
const capturedStatuses = ['captured', 'partially_refunded', 'refunded']
const attentionStatuses = ['failed', 'voided']

function statusLabel(status: string) { return status.replaceAll('_', ' ') }
function moneyTotal(records: WorkspacePayment[]) {
  if (records.length === 0) return '—'
  const byCurrency = new Map<string, number>()
  for (const record of records) byCurrency.set(record.currency, (byCurrency.get(record.currency) || 0) + (Number(record.amount) || 0))
  if (byCurrency.size !== 1) return `${records.length} payment${records.length === 1 ? '' : 's'}`
  const [currency, amount] = [...byCurrency.entries()][0]
  try { return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount) }
  catch { return `${currency} ${amount.toFixed(2)}` }
}
function paymentMatchesFilter(payment: WorkspacePayment, filter: PaymentFilter) {
  if (filter === 'in_progress') return activeStatuses.includes(payment.status)
  if (filter === 'captured') return capturedStatuses.includes(payment.status)
  if (filter === 'attention') return attentionStatuses.includes(payment.status)
  return true
}

export default function PaymentsPage({
  payments, paymentsLoading, paymentsError, proposals, proposalsLoading, proposalsError,
  role, busy, onRefresh, onOpenMilestone, onOverview, onRefundApprove, onRefundReject,
}: {
  payments: WorkspacePayment[]; paymentsLoading: boolean; paymentsError: string
  proposals: RefundProposal[]; proposalsLoading: boolean; proposalsError: string
  role: User['role']; busy: boolean; onRefresh: () => void
  onOpenMilestone: (payment: WorkspacePayment) => void; onOverview: () => void
  onRefundApprove: (proposal: RefundProposal) => void; onRefundReject: (proposal: RefundProposal) => void
}) {
  const [filter, setFilter] = useState<PaymentFilter>('all')
  const [search, setSearch] = useState('')
  const pending = payments.filter((payment) => activeStatuses.includes(payment.status))
  const paid = payments.filter((payment) => capturedStatuses.includes(payment.status))
  const needsAttention = payments.filter((payment) => attentionStatuses.includes(payment.status))
  const visiblePayments = useMemo(() => payments.filter((payment) => paymentMatchesFilter(payment, filter) && (!search.trim() || `${payment.project_title} ${payment.milestone_title} ${payment.status} ${payment.currency} ${payment.id}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))), [payments, filter, search])
  const filters: { key: PaymentFilter; label: string; count: number }[] = [
    { key: 'all', label: 'All payments', count: payments.length },
    { key: 'in_progress', label: 'Pending', count: pending.length },
    { key: 'captured', label: 'Captured', count: paid.length },
    { key: 'attention', label: 'Needs attention', count: needsAttention.length },
  ]

  return <>
    <div className="page-heading workspace-page-heading payments-heading">
      <div><span className="eyebrow">WORKSPACE / PAYMENTS</span><h1>Payments</h1><p>Manage PayPal transactions linked to your project milestones.</p></div>
      <div className="payments-heading-actions"><button type="button" className="secondary-button" onClick={onRefresh} disabled={paymentsLoading || proposalsLoading}>↻ Refresh</button><button type="button" className="payments-primary-action" onClick={onOverview}>Manage projects <span aria-hidden="true">＋</span></button></div>
    </div>

    <section className="payments-summary" aria-label="Payment totals">
      <article className="surface payment-metric pending"><div className="payment-metric-heading"><span>Pending</span><i aria-hidden="true">◷</i></div><strong>{moneyTotal(pending)}</strong><small>{pending.length} payment{pending.length === 1 ? '' : 's'} awaiting the next step</small></article>
      <article className="surface payment-metric paid"><div className="payment-metric-heading"><span>Captured</span><i aria-hidden="true">✓</i></div><strong>{moneyTotal(paid)}</strong><small>{paid.length} completed payment{paid.length === 1 ? '' : 's'}, including refunds</small></article>
      <article className="surface payment-metric attention"><div className="payment-metric-heading"><span>Needs attention</span><i aria-hidden="true">!</i></div><strong>{moneyTotal(needsAttention)}</strong><small>{needsAttention.length} failed or voided payment{needsAttention.length === 1 ? '' : 's'}</small></article>
    </section>

    <section className="surface workspace-data-card payments-ledger-card">
      <div className="payments-ledger-heading"><div><span className="eyebrow">PAYMENT TRANSACTIONS</span><h2>Recent transactions</h2><p>Payments attached to your project milestones.</p></div><span className="payments-record-count">{visiblePayments.length} of {payments.length} records</span></div>
      <div className="payments-toolbar">
        <div className="payment-filter-tabs" role="group" aria-label="Filter payments">
          {filters.map((item) => <button type="button" aria-pressed={filter === item.key} className={filter === item.key ? 'active' : ''} key={item.key} onClick={() => setFilter(item.key)}>{item.label}<span>{item.count}</span></button>)}
        </div>
        <label className="payment-search"><span aria-hidden="true">⌕</span><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search project or milestone" aria-label="Search payments"/>{search && <button type="button" onClick={() => setSearch('')} aria-label="Clear search">×</button>}</label>
      </div>

      {paymentsLoading ? <div className="workspace-empty" role="status">Loading payment records…</div>
        : paymentsError ? <div className="workspace-empty error" role="alert">{paymentsError}<button className="text-button" type="button" onClick={onRefresh}>Try again</button></div>
          : payments.length === 0 ? <div className="workspace-empty payments-empty"><span className="payments-empty-icon">$</span><h3>No payment records yet</h3><p>Payment records appear after a client creates a PayPal order for an agreed milestone.</p><button type="button" className="payments-primary-action" onClick={onOverview}>View projects <span aria-hidden="true">→</span></button></div>
            : visiblePayments.length === 0 ? <div className="workspace-empty">No payments match this search and status filter.</div>
              : <div className="payment-ledger-wrap"><table className="payment-ledger">
                <thead><tr><th>Project</th><th>Milestone</th><th>Amount</th><th>Refunded</th><th>Status</th><th>Last updated</th><th><span className="sr-only">Action</span></th></tr></thead>
                <tbody>{visiblePayments.map((payment) => <tr key={payment.id}>
                  <td><strong>{payment.project_title}</strong><span className="payment-record-id">Record {payment.id.slice(0, 8)}</span></td>
                  <td>{payment.milestone_title}</td>
                  <td className="ledger-amount">{payment.currency} {payment.amount}</td>
                  <td className="ledger-amount refunded-amount">{Number(payment.refunded_amount || 0) > 0 ? `${payment.currency} ${payment.refunded_amount}` : '—'}</td>
                  <td><span className={`payment-status-pill status-${payment.status}`}><i/>{statusLabel(payment.status)}</span></td>
                  <td>{new Date(payment.updated_at).toLocaleString()}</td>
                  <td><button type="button" className="payment-row-action" onClick={() => onOpenMilestone(payment)}>Open milestone <span aria-hidden="true">↗</span></button></td>
                </tr>)}</tbody>
              </table></div>}
      <p className="payment-ledger-note">TrustFlow coordinates PayPal transactions; it does not provide legal escrow. Payment operations remain available from each milestone.</p>
    </section>
    {role === 'client' && <Suspense fallback={<section className="surface refund-review-section" role="status">Loading refund review…</section>}>
      <RefundProposalsGrid proposals={proposals} loading={proposalsLoading} error={proposalsError} busy={busy} onApprove={onRefundApprove} onReject={onRefundReject} onRefresh={onRefresh}/>
    </Suspense>}
  </>
}
