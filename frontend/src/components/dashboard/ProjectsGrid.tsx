import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ClientSideRowModelModule,
  CsvExportModule,
  ModuleRegistry,
  NumberFilterModule,
  TextFilterModule,
  createGrid,
  themeQuartz,
  type ColDef,
  type GridApi,
  type ICellRendererParams,
  type ValueFormatterParams,
} from 'ag-grid-community'
import type { Project, User, WorkspaceActivity } from '../../api/assessment'

ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  CsvExportModule,
  NumberFilterModule,
  TextFilterModule,
])

type ProjectRow = Project & {
  collaborator: string
  statusLabel: string
  actionCount: number
  actionSummary: string
  lastUpdated: string
  lastUpdatedTimestamp: number
  progressPercent: number
}

type ProjectsGridProps = {
  projects: Project[]
  activity: WorkspaceActivity[]
  role: User['role']
  busy: boolean
  onOpen: (id: string) => void
  onEdit: (id: string) => void
  onAccept: (id: string) => void
  onDecline: (id: string) => void
  onClearFilters: () => void
}

function makeProjectRow(project: Project, role: User['role'], activity?: WorkspaceActivity): ProjectRow {
  const invited = project.membership_status === 'invited'
  const reviewCount = project.submitted_count || 0
  const revisionCount = project.revision_count || 0
  const decisionCount = project.decision_due_count || 0
  const actionCount = project.status === 'cancelled' ? 0 : invited ? (role === 'freelancer' ? 1 : 0) : role === 'client' ? Math.max(reviewCount, decisionCount) : revisionCount
  let actionSummary = project.status === 'cancelled' ? 'Project cancelled' : 'No pending actions'
  if (invited) actionSummary = role === 'freelancer' ? 'Invitation to accept' : 'Invitation sent'
  else if (role === 'client') {
    actionSummary = [
      reviewCount ? `${reviewCount} to review` : '',
      decisionCount ? `${decisionCount} decisions due` : '',
    ].filter(Boolean).join(' · ') || actionSummary
  } else if (revisionCount) {
    actionSummary = `${revisionCount} revision${revisionCount === 1 ? '' : 's'} requested`
  }

  const needsReview = role === 'client' && (reviewCount > 0 || decisionCount > 0)
  const needsRevision = role === 'freelancer' && revisionCount > 0
  const lastUpdatedTimestamp = activity ? new Date(activity.created_at).getTime() : 0

  return {
    ...project,
    collaborator: role === 'client'
      ? project.freelancer_name || 'Not assigned'
      : project.client_name || 'Not listed',
    statusLabel: project.status === 'cancelled' ? 'Cancelled' : invited
      ? role === 'freelancer' ? 'Invitation received' : 'Invitation sent'
      : project.membership_status === 'declined' ? 'Declined' : needsReview ? 'Needs attention' : needsRevision ? 'Revision requested' : 'Active',
    actionCount,
    actionSummary,
    lastUpdated: activity ? new Intl.DateTimeFormat(undefined, { month: 'numeric', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(activity.created_at)) : 'No recent activity',
    lastUpdatedTimestamp,
    progressPercent: Math.max(0, Math.min(100, project.progress_percent || 0)),
  }
}

function makeStatusChip(row: ProjectRow, label: string) {
  const chip = document.createElement('span')
  const tone = row.revision_count
    ? 'needs-revision'
    : row.submitted_count || row.decision_due_count
      ? 'needs-review'
      : row.membership_status === 'accepted'
        ? 'on-track'
        : ''
  chip.className = `project-grid-status ${row.membership_status} ${tone} ${row.actionCount ? 'needs-attention' : ''}`
  chip.textContent = label
  return chip
}

function makeRowIconButton(label: string, pathData: string) {
  const button = document.createElement('button')
  button.type = 'button'
  button.className = 'project-grid-action-icon'
  button.setAttribute('aria-label', label)
  button.title = label
  const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  icon.setAttribute('viewBox', '0 0 24 24')
  icon.setAttribute('aria-hidden', 'true')
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
  path.setAttribute('d', pathData)
  icon.append(path)
  button.append(icon)
  return button
}

export default function ProjectsGrid({ projects, activity, role, busy, onOpen, onEdit, onAccept, onDecline, onClearFilters }: ProjectsGridProps) {
  const gridElement = useRef<HTMLDivElement>(null)
  const gridApi = useRef<GridApi<ProjectRow> | null>(null)
  const handlers = useRef({ onOpen, onEdit, onAccept, onDecline, busy })
  const [visibleCount, setVisibleCount] = useState(projects.length)
  const [hasColumnFilters, setHasColumnFilters] = useState(false)

  const latestActivity = useMemo(() => {
    const byProject = new Map<string, WorkspaceActivity>()
    for (const item of activity) {
      const previous = byProject.get(item.project_id)
      if (!previous || new Date(item.created_at).getTime() > new Date(previous.created_at).getTime()) byProject.set(item.project_id, item)
    }
    return byProject
  }, [activity])
  const rows = useMemo(() => projects.map((project) => makeProjectRow(project, role, latestActivity.get(project.id))), [projects, role, latestActivity])

  const columnDefs = useMemo<ColDef<ProjectRow>[]>(() => [
    {
      field: 'title',
      headerName: 'Project Name',
      flex: 1.35,
      minWidth: 190,
      filter: 'agTextColumnFilter',
      cellClass: 'project-grid-title',
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
      flex: 0.85,
      minWidth: 145,
      filter: 'agTextColumnFilter',
      cellRenderer: ({ value }: ICellRendererParams<ProjectRow>) => {
        const person = document.createElement('span')
        person.className = 'project-grid-person'
        const avatar = document.createElement('i')
        avatar.textContent = String(value || '?').trim().slice(0, 1).toUpperCase()
        const name = document.createElement('span')
        name.textContent = String(value || 'Not listed')
        person.append(avatar, name)
        return person
      },
    },
    {
      field: 'statusLabel',
      headerName: 'Status',
      flex: 1,
      minWidth: 164,
      filter: 'agTextColumnFilter',
      cellRenderer: ({ data, value }: ICellRendererParams<ProjectRow>) => {
        if (!data) return ''
        const status = document.createElement('span')
        status.className = 'project-grid-status-stack'
        status.append(makeStatusChip(data, String(value)))
        if (data.actionCount) {
          const detail = document.createElement('small')
          detail.textContent = data.actionSummary
          status.append(detail)
        }
        return status
      },
    },
    {
      field: 'milestone_count',
      headerName: 'Milestones',
      width: 150,
      filter: 'agNumberColumnFilter',
      valueFormatter: ({ value }: ValueFormatterParams<ProjectRow>) => `${value ?? 0}`,
      cellRenderer: ({ data, value }: ICellRendererParams<ProjectRow>) => {
        if (!data) return ''
        const progress = document.createElement('span')
        progress.className = 'project-grid-milestone-progress'
        const count = document.createElement('strong')
        count.textContent = String(value ?? 0)
        progress.append(count)
        if (Number(value || 0) > 0) {
          const progressTone = data.progressPercent >= 100
            ? 'complete'
            : data.revision_count
              ? 'revision'
              : data.submitted_count || data.decision_due_count
                ? 'review'
                : data.progressPercent > 0
                  ? 'in-progress'
                  : 'not-started'
          const track = document.createElement('span')
          track.className = `project-grid-progress-track milestone-${progressTone}`
          track.setAttribute('role', 'progressbar')
          track.setAttribute('aria-label', `${data.progressPercent}% milestone progress for ${data.title}; ${progressTone.replace('-', ' ')}`)
          track.setAttribute('aria-valuemin', '0')
          track.setAttribute('aria-valuemax', '100')
          track.setAttribute('aria-valuenow', String(data.progressPercent))
          track.title = `${data.progressPercent}% · ${progressTone.replace('-', ' ')}`
          const fill = document.createElement('i')
          fill.style.width = `${data.progressPercent}%`
          track.append(fill)
          progress.append(track)
        } else {
          const empty = document.createElement('span')
          empty.className = 'project-grid-no-milestones'
          empty.textContent = '—'
          progress.append(empty)
        }
        return progress
      },
    },
    {
      field: 'active_payment_count',
      headerName: 'Payments',
      width: 112,
      filter: 'agNumberColumnFilter',
      cellClass: 'project-grid-payments',
      valueFormatter: ({ value }: ValueFormatterParams<ProjectRow>) => Number(value || 0) ? String(value) : '—',
    },
    {
      field: 'lastUpdated',
      headerName: 'Last Updated',
      width: 148,
      filter: 'agTextColumnFilter',
      cellClass: 'project-grid-updated',
      comparator: (_valueA, _valueB, nodeA, nodeB) => (nodeA.data?.lastUpdatedTimestamp || 0) - (nodeB.data?.lastUpdatedTimestamp || 0),
    },
    {
      colId: 'action',
      headerName: '',
      width: role === 'freelancer' ? 210 : 122,
      sortable: false,
      filter: false,
      resizable: false,
      suppressCsvExport: true,
      cellClass: 'project-grid-actions-cell',
      cellRenderer: ({ data }: ICellRendererParams<ProjectRow>) => {
        if (!data) return ''
        const invited = role === 'freelancer' && data.membership_status === 'invited'
        if (invited) {
          const actions = document.createElement('span')
          actions.className = 'project-grid-row-actions'
          const accept = document.createElement('button')
          accept.type = 'button'
          accept.className = 'project-grid-action accept'
          accept.textContent = 'Accept invite'
          accept.disabled = handlers.current.busy
          accept.setAttribute('aria-label', `Accept invitation to ${data.title}`)
          accept.addEventListener('click', (event) => {
            event.stopPropagation()
            handlers.current.onAccept(data.id)
          })
          const decline = document.createElement('button')
          decline.type = 'button'
          decline.className = 'project-grid-action'
          decline.textContent = 'Decline'
          decline.disabled = handlers.current.busy
          decline.setAttribute('aria-label', `Decline invitation to ${data.title}`)
          decline.addEventListener('click', (event) => {
            event.stopPropagation()
            handlers.current.onDecline(data.id)
          })
          actions.append(accept, decline)
          return actions
        }
        const actions = document.createElement('span')
        actions.className = 'project-grid-row-actions'
        const view = makeRowIconButton(`View ${data.title}`, 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z')
        view.addEventListener('click', (event) => {
          event.stopPropagation()
          handlers.current.onOpen(data.id)
        })
        actions.append(view)
        if (role === 'client' && data.status === 'active' && !['declined', 'cancelled'].includes(data.membership_status)) {
          const edit = makeRowIconButton(`Edit a milestone in ${data.title}`, 'm4 16.5V20h3.5L19 8.5 15.5 5 4 16.5Zm9.8-9.9 3.5 3.5')
          edit.addEventListener('click', (event) => {
            event.stopPropagation()
            handlers.current.onEdit(data.id)
          })
          actions.append(edit)
        }
        return actions
      },
    },
  ], [role])

  useEffect(() => {
    handlers.current = { onOpen, onEdit, onAccept, onDecline, busy }
  }, [onOpen, onEdit, onAccept, onDecline, busy])

  useEffect(() => {
    if (!gridElement.current) return
    const syncGridSummary = (api: GridApi<ProjectRow>) => {
      const displayed = api.getDisplayedRowCount()
      setVisibleCount((current) => current === displayed ? current : displayed)
    }

    const api = createGrid<ProjectRow>(gridElement.current, {
      theme: themeQuartz,
      columnDefs,
      rowData: [],
      defaultColDef: {
        sortable: true,
        resizable: true,
        floatingFilter: false,
      },
      getRowId: ({ data }) => data.id,
      headerHeight: 44,
      rowHeight: 62,
      domLayout: 'autoHeight',
      onGridReady: ({ api: readyApi }) => {
        gridApi.current = readyApi
        syncGridSummary(readyApi)
      },
      onModelUpdated: ({ api: model }) => syncGridSummary(model),
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
    gridApi.current?.refreshCells({ columns: ['action'], force: true })
  }, [busy])

  function clearGridFilters() {
    gridApi.current?.setFilterModel(null)
    onClearFilters()
  }

  function exportProjects() {
    gridApi.current?.exportDataAsCsv({
      fileName: 'trustflow-projects.csv',
      columnKeys: ['title', 'collaborator', 'statusLabel', 'actionSummary', 'milestone_count', 'progressPercent', 'active_payment_count', 'lastUpdated'],
    })
  }

  const hasFilters = hasColumnFilters

  return <div className="projects-grid-wrap">
    <div className="projects-grid-toolbar">
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
      aria-label="Projects"
    />
    {visibleCount === 0 && projects.length > 0 && <div className="projects-grid-empty">
      <strong>No projects match these filters</strong>
      <span>Clear the search or column filters to see your projects.</span>
      <button type="button" className="projects-grid-text-button" onClick={clearGridFilters}>Clear filters</button>
    </div>}
  </div>
}
