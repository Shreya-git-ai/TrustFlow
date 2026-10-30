import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ClientSideRowModelModule,
  ModuleRegistry,
  NumberFilterModule,
  PaginationModule,
  QuickFilterModule,
  TextFilterModule,
  TooltipModule,
  createGrid,
  themeQuartz,
  type ColDef,
  type GridApi,
  type ICellRendererParams,
  type ValueFormatterParams,
} from 'ag-grid-community'
import type { RefundProposal } from '../../api/assessment'

ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  NumberFilterModule,
  PaginationModule,
  QuickFilterModule,
  TextFilterModule,
  TooltipModule,
])

type Props = {
  proposals: RefundProposal[]
  loading: boolean
  error: string
  busy: boolean
  onApprove: (proposal: RefundProposal) => void
  onReject: (proposal: RefundProposal) => void
  onRefresh: () => void
}

type QueueFilter = 'pending' | 'processing' | 'history' | 'all'

function statusChip(status: RefundProposal['status']) {
  const chip = document.createElement('span')
  chip.className = `refund-grid-status ${status}`
  chip.textContent = status.replaceAll('_', ' ')
  return chip
}

export default function RefundProposalsGrid({ proposals, loading, error, busy, onApprove, onReject, onRefresh }: Props) {
  const gridElement = useRef<HTMLDivElement>(null)
  const gridApi = useRef<GridApi<RefundProposal> | null>(null)
  const handlers = useRef({ onApprove, onReject, busy })
  const [queueFilter, setQueueFilter] = useState<QueueFilter>('pending')
  const [query, setQuery] = useState('')
  const [hasColumnFilters, setHasColumnFilters] = useState(false)

  const pendingCount = proposals.filter((proposal) => proposal.status === 'pending').length
  const processingCount = proposals.filter((proposal) => proposal.status === 'processing').length
  const historyCount = proposals.filter((proposal) => ['refunded', 'rejected', 'failed'].includes(proposal.status)).length
  const filteredRows = useMemo(() => proposals.filter((proposal) => {
    if (queueFilter === 'pending') return proposal.status === 'pending'
    if (queueFilter === 'processing') return proposal.status === 'processing'
    if (queueFilter === 'history') return ['refunded', 'rejected', 'failed'].includes(proposal.status)
    return true
  }), [proposals, queueFilter])
  const [displayedCount, setDisplayedCount] = useState(filteredRows.length)
  const [gridRows, setGridRows] = useState(Math.min(filteredRows.length, 8))

  const columnDefs = useMemo<ColDef<RefundProposal>[]>(() => [
    {
      field: 'project_title',
      headerName: 'Project / milestone',
      flex: 1.05,
      minWidth: 175,
      filter: 'agTextColumnFilter',
      getQuickFilterText: ({ data }) => `${data?.project_title || ''} ${data?.milestone_title || ''}`,
      cellRenderer: ({ data }: ICellRendererParams<RefundProposal>) => {
        if (!data) return ''
        const cell = document.createElement('span')
        cell.className = 'refund-grid-project'
        const project = document.createElement('strong')
        project.textContent = data.project_title
        const milestone = document.createElement('small')
        milestone.textContent = data.milestone_title
        cell.append(project, milestone)
        return cell
      },
    },
    {
      colId: 'refund_amount',
      headerName: 'Proposed refund',
      width: 143,
      filter: 'agNumberColumnFilter',
      valueGetter: ({ data }) => Number(data?.amount || 0),
      valueFormatter: ({ value, data }: ValueFormatterParams<RefundProposal>) => {
        if (!data) return ''
        try {
          return new Intl.NumberFormat(undefined, { style: 'currency', currency: data.currency }).format(Number(value))
        } catch {
          return `${data.currency} ${Number(value).toFixed(2)}`
        }
      },
      cellClass: 'refund-grid-amount',
    },
    {
      field: 'reason',
      headerName: 'Agent recommendation',
      flex: 1.3,
      minWidth: 220,
      filter: 'agTextColumnFilter',
      tooltipField: 'reason',
      cellRenderer: ({ data }: ICellRendererParams<RefundProposal>) => {
        if (!data) return ''
        const cell = document.createElement('span')
        cell.className = 'refund-grid-reason'
        cell.textContent = data.reason
        cell.title = data.reason
        return cell
      },
    },
    {
      colId: 'support_ticket',
      headerName: 'Linked ticket',
      minWidth: 125,
      width: 145,
      sortable: false,
      filter: false,
      valueGetter: ({ data }) => data?.zendesk_ticket_id
        ? `Zendesk #${data.zendesk_ticket_id}`
        : data?.slack_channel_id ? `Slack ${data.slack_channel_id}` : 'Not linked',
    },
    {
      field: 'proposed_at',
      headerName: 'Proposed',
      width: 128,
      filter: false,
      valueFormatter: ({ value }: ValueFormatterParams<RefundProposal>) => value
        ? new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value))
        : '',
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 122,
      filter: 'agTextColumnFilter',
      cellRenderer: ({ value }: ICellRendererParams<RefundProposal>) => value ? statusChip(value) : '',
    },
    {
      colId: 'review',
      headerName: 'Merchant review',
      width: 185,
      sortable: false,
      filter: false,
      resizable: false,
      suppressCsvExport: true,
      cellRenderer: ({ data }: ICellRendererParams<RefundProposal>) => {
        if (!data) return ''
        const actions = document.createElement('span')
        actions.className = 'refund-grid-actions'
        if (data.status !== 'pending') {
          if (data.status === 'processing') {
            const retry = document.createElement('button')
            retry.type = 'button'
            retry.className = 'refund-grid-retry'
            retry.textContent = 'Retry PayPal check'
            retry.disabled = handlers.current.busy
            retry.setAttribute('aria-label', `Retry PayPal confirmation for ${data.project_title}`)
            retry.addEventListener('click', (event) => {
              event.stopPropagation()
              handlers.current.onApprove(data)
            })
            actions.append(retry)
            return actions
          }
          const done = document.createElement('span')
          done.className = 'refund-grid-reviewed'
          done.textContent = 'Reviewed'
          actions.append(done)
          return actions
        }
        const approve = document.createElement('button')
        approve.type = 'button'
        approve.className = 'refund-grid-approve'
        approve.textContent = 'Approve refund'
        approve.disabled = handlers.current.busy
        approve.setAttribute('aria-label', `Approve refund of ${data.currency} ${data.amount} for ${data.project_title}`)
        approve.addEventListener('click', (event) => {
          event.stopPropagation()
          handlers.current.onApprove(data)
        })
        const reject = document.createElement('button')
        reject.type = 'button'
        reject.className = 'refund-grid-reject'
        reject.textContent = 'Reject'
        reject.disabled = handlers.current.busy
        reject.setAttribute('aria-label', `Reject refund proposal for ${data.project_title}`)
        reject.addEventListener('click', (event) => {
          event.stopPropagation()
          handlers.current.onReject(data)
        })
        actions.append(approve, reject)
        return actions
      },
    },
  ], [])

  useEffect(() => {
    handlers.current = { onApprove, onReject, busy }
  }, [onApprove, onReject, busy])

  useEffect(() => {
    if (!gridElement.current) return
    const syncGridLayout = (api: GridApi<RefundProposal>) => {
      const count = api.getDisplayedRowCount()
      setDisplayedCount(count)
      setGridRows(count === 0 ? 3 : Math.min(count, api.paginationGetPageSize() || 8))
    }
    const api = createGrid<RefundProposal>(gridElement.current, {
      theme: themeQuartz,
      columnDefs,
      rowData: [],
      defaultColDef: { sortable: true, resizable: true, floatingFilter: true },
      getRowId: ({ data }) => data.id,
      headerHeight: 43,
      rowHeight: 64,
      pagination: true,
      paginationPageSize: 8,
      paginationPageSizeSelector: [8, 15, 25],
      onModelUpdated: ({ api: model }) => syncGridLayout(model),
      onPaginationChanged: ({ api: model }) => syncGridLayout(model),
      onFilterChanged: ({ api: model }) => setHasColumnFilters(model.isAnyFilterPresent()),
    })
    gridApi.current = api
    return () => {
      api.destroy()
      gridApi.current = null
    }
  }, [columnDefs])

  useEffect(() => {
    gridApi.current?.setGridOption('rowData', filteredRows)
  }, [filteredRows])

  useEffect(() => {
    gridApi.current?.setGridOption('quickFilterText', query.trim())
  }, [query])

  useEffect(() => {
    gridApi.current?.refreshCells({ columns: ['review'], force: true })
  }, [busy])

  function clearFilters() {
    setQuery('')
    gridApi.current?.setFilterModel(null)
    gridApi.current?.setGridOption('quickFilterText', '')
  }

  const hasFilters = Boolean(query.trim()) || hasColumnFilters

  return <section className="refund-review-section">
    <div className="refund-review-heading">
      <div><span className="eyebrow">MERCHANT REVIEW</span><h3>Agent-proposed refunds</h3><p>Refunds are never sent until you approve them. PayPal confirms completion asynchronously.</p></div>
      <button className="secondary-button" type="button" onClick={onRefresh} disabled={loading}>↻ Refresh</button>
    </div>
    <div className="refund-queue-tabs" role="tablist" aria-label="Filter refund proposals">
      <button type="button" role="tab" aria-selected={queueFilter === 'pending'} className={queueFilter === 'pending' ? 'active' : ''} onClick={() => setQueueFilter('pending')}>Pending <span>{pendingCount}</span></button>
      <button type="button" role="tab" aria-selected={queueFilter === 'processing'} className={queueFilter === 'processing' ? 'active' : ''} onClick={() => setQueueFilter('processing')}>Processing <span>{processingCount}</span></button>
      <button type="button" role="tab" aria-selected={queueFilter === 'history'} className={queueFilter === 'history' ? 'active' : ''} onClick={() => setQueueFilter('history')}>History <span>{historyCount}</span></button>
      <button type="button" role="tab" aria-selected={queueFilter === 'all'} className={queueFilter === 'all' ? 'active' : ''} onClick={() => setQueueFilter('all')}>All <span>{proposals.length}</span></button>
    </div>
    {!loading && !error && proposals.length > 0 && <div className="refund-grid-toolbar">
      <label className="refund-grid-search"><span aria-hidden="true">⌕</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search proposals, payments, or tickets" aria-label="Search refund proposals"/>{query && <button type="button" onClick={() => setQuery('')} aria-label="Clear search">×</button>}</label>
      <div className="refund-grid-toolbar-actions"><span role="status">{displayedCount} shown</span>{hasFilters && <button type="button" className="refund-grid-clear" onClick={clearFilters}>Clear filters</button>}</div>
    </div>}
    <div className="refund-grid-container">
      <div ref={gridElement} className="refund-proposals-grid" style={{ height: `${gridRows * 64 + 123}px` }} aria-label="Agent-proposed refunds"/>
      {loading ? <div className="refund-grid-empty overlay" role="status">Loading refund proposals…</div>
        : error ? <div className="refund-grid-empty overlay error" role="alert">{error}<button type="button" className="text-button" onClick={onRefresh}>Try again</button></div>
          : proposals.length === 0 ? <div className="refund-grid-empty overlay"><strong>No agent proposals yet</strong><span>When the refund agent flags a captured payment, it will appear here for your review.</span></div>
          : displayedCount === 0 ? <div className="refund-grid-empty overlay"><strong>No proposals in this view</strong><span>Choose another status filter or clear the grid filters.</span><button className="refund-grid-clear" type="button" onClick={() => { clearFilters(); setQueueFilter('all') }}>Show all proposals</button></div>
              : null}
    </div>
  </section>
}
