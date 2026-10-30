import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ClientSideRowModelModule,
  CsvExportModule,
  ModuleRegistry,
  NumberFilterModule,
  PaginationModule,
  QuickFilterModule,
  TextFilterModule,
  createGrid,
  themeQuartz,
  type ColDef,
  type GridApi,
  type ICellRendererParams,
  type ValueFormatterParams,
} from 'ag-grid-community'
import type { Project, User } from '../../api/assessment'

ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  CsvExportModule,
  NumberFilterModule,
  PaginationModule,
  QuickFilterModule,
  TextFilterModule,
])

type ProjectRow = Project & {
  collaborator: string
  statusLabel: string
  actionCount: number
  actionSummary: string
  paymentSummary: string
}

type ProjectsGridProps = {
  projects: Project[]
  role: User['role']
  busy: boolean
  onOpen: (id: string) => void
  onAccept: (id: string) => void
}

const PAGE_SIZE = 8

function makeProjectRow(project: Project, role: User['role']): ProjectRow {
  const invited = project.membership_status === 'invited'
  const reviewCount = project.submitted_count || 0
  const revisionCount = project.revision_count || 0
  const decisionCount = project.decision_due_count || 0
  const actionCount = invited ? (role === 'freelancer' ? 1 : 0) : role === 'client' ? reviewCount + decisionCount : revisionCount
  let actionSummary = 'No pending actions'
  if (invited) actionSummary = role === 'freelancer' ? 'Invitation to accept' : 'Invitation pending'
  else if (role === 'client') {
    actionSummary = [
      reviewCount ? `${reviewCount} to review` : '',
      decisionCount ? `${decisionCount} decisions due` : '',
    ].filter(Boolean).join(' · ') || actionSummary
  } else if (revisionCount) {
    actionSummary = `${revisionCount} revision${revisionCount === 1 ? '' : 's'} requested`
  }

  return {
    ...project,
    collaborator: role === 'client'
      ? project.freelancer_name || 'Not assigned'
      : project.client_name || 'Not listed',
    statusLabel: invited
      ? 'Invitation pending'
      : project.membership_status === 'declined' ? 'Declined' : 'Active',
    actionCount,
    actionSummary,
    paymentSummary: project.active_payment_count
      ? `${project.active_payment_count} active`
      : 'None active',
  }
}

function makeStatusChip(row: ProjectRow, label: string) {
  const chip = document.createElement('span')
  chip.className = `project-grid-status ${row.membership_status}`
  chip.textContent = label
  return chip
}

export default function ProjectsGrid({ projects, role, busy, onOpen, onAccept }: ProjectsGridProps) {
  const gridElement = useRef<HTMLDivElement>(null)
  const gridApi = useRef<GridApi<ProjectRow> | null>(null)
  const handlers = useRef({ onOpen, onAccept, busy })
  const [query, setQuery] = useState('')
  const [visibleRows, setVisibleRows] = useState(Math.min(projects.length, PAGE_SIZE))
  const [visibleCount, setVisibleCount] = useState(projects.length)
  const [hasColumnFilters, setHasColumnFilters] = useState(false)

  const rows = useMemo(() => projects.map((project) => makeProjectRow(project, role)), [projects, role])

  const columnDefs = useMemo<ColDef<ProjectRow>[]>(() => [
    {
      field: 'title',
      headerName: 'Project',
      flex: 1.35,
      minWidth: 190,
      filter: 'agTextColumnFilter',
      cellClass: 'project-grid-title',
      getQuickFilterText: ({ data }) => `${data?.title || ''} ${data?.description || ''}`,
      cellRenderer: ({ data }: ICellRendererParams<ProjectRow>) => {
        if (!data) return ''
        const wrapper = document.createElement('span')
        wrapper.className = 'project-grid-project'
        const title = document.createElement('strong')
        title.textContent = data.title
        wrapper.append(title)
        if (data.description) {
          const description = document.createElement('small')
          description.textContent = data.description
          wrapper.append(description)
        }
        return wrapper
      },
    },
    {
      field: 'collaborator',
      headerName: role === 'client' ? 'Freelancer' : 'Client',
      flex: 0.9,
      minWidth: 130,
      filter: 'agTextColumnFilter',
    },
    {
      field: 'actionSummary',
      headerName: 'Needs attention',
      flex: 1,
      minWidth: 170,
      filter: 'agTextColumnFilter',
      sort: 'desc',
      comparator: (_valueA, _valueB, nodeA, nodeB) =>
        (nodeA.data?.actionCount || 0) - (nodeB.data?.actionCount || 0),
      cellClass: 'project-grid-attention',
      cellRenderer: ({ data }: ICellRendererParams<ProjectRow>) => {
        if (!data) return ''
        const attention = document.createElement('span')
        attention.className = `project-grid-attention-pill ${data.actionCount ? 'has-actions' : ''}`
        attention.textContent = data.actionSummary
        return attention
      },
    },
    {
      field: 'milestone_count',
      headerName: 'Milestones',
      width: 112,
      filter: 'agNumberColumnFilter',
      valueFormatter: ({ value }: ValueFormatterParams<ProjectRow>) => String(value ?? 0),
    },
    {
      field: 'paymentSummary',
      headerName: 'Payments',
      width: 118,
      filter: 'agTextColumnFilter',
      cellClass: 'project-grid-payments',
    },
    {
      field: 'statusLabel',
      headerName: 'Status',
      width: 152,
      filter: 'agTextColumnFilter',
      cellRenderer: ({ data, value }: ICellRendererParams<ProjectRow>) =>
        data ? makeStatusChip(data, String(value)) : '',
    },
    {
      colId: 'action',
      headerName: '',
      width: 132,
      sortable: false,
      filter: false,
      resizable: false,
      suppressCsvExport: true,
      cellRenderer: ({ data }: ICellRendererParams<ProjectRow>) => {
        if (!data) return ''
        const invited = role === 'freelancer' && data.membership_status === 'invited'
        const button = document.createElement('button')
        button.type = 'button'
        button.className = invited ? 'project-grid-action accept' : 'project-grid-action open'
        button.textContent = invited ? 'Accept invite' : 'Open project'
        button.disabled = invited && handlers.current.busy
        button.setAttribute('aria-label', `${invited ? 'Accept invitation to' : 'Open'} ${data.title}`)
        button.addEventListener('click', (event) => {
          event.stopPropagation()
          if (invited) handlers.current.onAccept(data.id)
          else handlers.current.onOpen(data.id)
        })
        return button
      },
    },
  ], [role])

  useEffect(() => {
    handlers.current = { onOpen, onAccept, busy }
  }, [onOpen, onAccept, busy])

  useEffect(() => {
    if (!gridElement.current) return
    const syncGridSummary = (api: GridApi<ProjectRow>) => {
      const displayed = api.getDisplayedRowCount()
      const pageSize = api.paginationGetPageSize() || PAGE_SIZE
      setVisibleCount((current) => current === displayed ? current : displayed)
      setVisibleRows((current) => {
        const next = displayed === 0 ? Math.min(3, pageSize) : Math.min(displayed, pageSize)
        return current === next ? current : next
      })
    }

    const api = createGrid<ProjectRow>(gridElement.current, {
      theme: themeQuartz,
      columnDefs,
      rowData: [],
      defaultColDef: {
        sortable: true,
        resizable: true,
        floatingFilter: true,
      },
      getRowId: ({ data }) => data.id,
      headerHeight: 44,
      rowHeight: 62,
      pagination: true,
      paginationPageSize: PAGE_SIZE,
      paginationPageSizeSelector: [PAGE_SIZE, 15, 25],
      onGridReady: ({ api: readyApi }) => {
        gridApi.current = readyApi
        syncGridSummary(readyApi)
      },
      onModelUpdated: ({ api: model }) => syncGridSummary(model),
      onPaginationChanged: ({ api: model }) => syncGridSummary(model),
      onFilterChanged: ({ api: model }) => {
        setHasColumnFilters(model.isAnyFilterPresent())
        syncGridSummary(model)
      },
    })
    gridApi.current = api
    return () => {
      api.destroy()
      gridApi.current = null
    }
  }, [columnDefs])

  useEffect(() => {
    gridApi.current?.setGridOption('rowData', rows)
  }, [rows])

  useEffect(() => {
    gridApi.current?.setGridOption('quickFilterText', query.trim())
  }, [query])

  useEffect(() => {
    gridApi.current?.refreshCells({ columns: ['action'], force: true })
  }, [busy])

  function clearGridFilters() {
    setQuery('')
    gridApi.current?.setFilterModel(null)
    gridApi.current?.setGridOption('quickFilterText', '')
  }

  function exportProjects() {
    gridApi.current?.exportDataAsCsv({
      fileName: 'trustflow-projects.csv',
      columnKeys: ['title', 'collaborator', 'actionSummary', 'milestone_count', 'paymentSummary', 'statusLabel'],
    })
  }

  const hasFilters = Boolean(query.trim()) || hasColumnFilters

  return <div className="projects-grid-wrap">
    <div className="projects-grid-toolbar">
      <label className="projects-grid-search">
        <span aria-hidden="true">⌕</span>
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search projects, people, or actions"
          aria-label="Search projects, people, or actions"
        />
        {query && <button type="button" onClick={() => setQuery('')} aria-label="Clear search">×</button>}
      </label>
      <div className="projects-grid-tools">
        <span className="projects-grid-result-count" role="status">{visibleCount} of {projects.length} projects</span>
        {hasFilters && <button type="button" className="projects-grid-text-button" onClick={clearGridFilters}>Clear filters</button>}
        <button type="button" className="projects-grid-export" onClick={exportProjects} disabled={projects.length === 0}>
          <span aria-hidden="true">↓</span> Export CSV
        </button>
      </div>
    </div>
    <div
      ref={gridElement}
      className="projects-grid"
      style={{ height: `${visibleRows * 62 + 133}px` }}
      aria-label="Projects"
    />
    {visibleCount === 0 && projects.length > 0 && <div className="projects-grid-empty">
      <strong>No projects match these filters</strong>
      <span>Clear the search or column filters to see your projects.</span>
      <button type="button" className="projects-grid-text-button" onClick={clearGridFilters}>Clear filters</button>
    </div>}
  </div>
}
