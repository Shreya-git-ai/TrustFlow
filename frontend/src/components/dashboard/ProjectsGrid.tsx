import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ClientSideRowModelModule,
  ModuleRegistry,
  NumberFilterModule,
  PaginationModule,
  TextFilterModule,
  createGrid,
  themeQuartz,
  type ColDef,
  type GridApi,
  type ICellRendererParams,
} from 'ag-grid-community'
import type { Project, User } from '../../api/assessment'

ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  NumberFilterModule,
  PaginationModule,
  TextFilterModule,
])

type ProjectRow = Project & {
  collaborator: string
  statusLabel: string
}

type ProjectsGridProps = {
  projects: Project[]
  role: User['role']
  busy: boolean
  onOpen: (id: string) => void
  onAccept: (id: string) => void
}

export default function ProjectsGrid({ projects, role, busy, onOpen, onAccept }: ProjectsGridProps) {
  const gridElement = useRef<HTMLDivElement>(null)
  const gridApi = useRef<GridApi<ProjectRow> | null>(null)
  const handlers = useRef({ onOpen, onAccept, busy })
  const [visibleRows, setVisibleRows] = useState(Math.min(projects.length, 8))

  const rows = useMemo<ProjectRow[]>(() => projects.map((project) => ({
    ...project,
    collaborator: role === 'client'
      ? project.freelancer_name || 'Not assigned'
      : project.client_name || 'Not listed',
    statusLabel: project.membership_status === 'invited'
      ? 'Invitation pending'
      : project.membership_status === 'declined' ? 'Declined' : 'Active',
  })), [projects, role])

  const columnDefs = useMemo<ColDef<ProjectRow>[]>(() => [
    {
      field: 'title',
      headerName: 'Project',
      flex: 1.2,
      minWidth: 165,
      filter: true,
      cellClass: 'project-grid-title',
    },
    {
      field: 'collaborator',
      headerName: role === 'client' ? 'Freelancer' : 'Client',
      flex: 1,
      minWidth: 135,
      filter: true,
    },
    {
      field: 'milestone_count',
      headerName: 'Milestones',
      width: 112,
      filter: 'agNumberColumnFilter',
      valueFormatter: ({ value }) => String(value ?? 0),
    },
    {
      field: 'statusLabel',
      headerName: 'Status',
      width: 145,
      filter: true,
      cellRenderer: ({ data, value }: ICellRendererParams<ProjectRow>) => {
        if (!data) return ''
        const chip = document.createElement('span')
        chip.className = `project-grid-status ${data.membership_status}`
        chip.textContent = String(value)
        return chip
      },
    },
    {
      colId: 'action',
      headerName: '',
      width: 138,
      sortable: false,
      filter: false,
      resizable: false,
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
      headerHeight: 42,
      rowHeight: 58,
      pagination: true,
      paginationPageSize: 8,
      onModelUpdated: ({ api: model }) => {
        const count = Math.min(model.getDisplayedRowCount(), 8)
        setVisibleRows((current) => current === count ? current : count)
      },
      onPaginationChanged: ({ api: model }) => {
        const count = Math.min(model.getDisplayedRowCount(), 8)
        setVisibleRows((current) => current === count ? current : count)
      },
      onGridReady: (event) => { gridApi.current = event.api },
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

  return <div className="projects-grid-wrap">
    <div
      ref={gridElement}
      className="projects-grid"
      style={{ height: `${visibleRows * 58 + 128}px` }}
      aria-label="Projects"
    />
  </div>
}
