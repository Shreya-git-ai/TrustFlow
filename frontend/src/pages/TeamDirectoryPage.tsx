import { useMemo, useState } from 'react'
import type { Project, User } from '../api/assessment'

type DirectoryProject = Pick<Project, 'id' | 'title' | 'membership_status'>
type DirectoryMember = {
  name: string
  role: 'client' | 'freelancer'
  projects: DirectoryProject[]
}

export default function TeamDirectoryPage({ projects, role, onOpenProject }: {
  projects: Project[]
  role: User['role']
  onOpenProject: (id: string) => void
}) {
  const [search, setSearch] = useState('')
  const members = useMemo(() => {
    const byName = new Map<string, DirectoryMember>()
    for (const project of projects) {
      const name = role === 'client' ? project.freelancer_name : project.client_name
      if (!name?.trim()) continue
      const key = name.trim().toLocaleLowerCase()
      const member = byName.get(key) || {
        name: name.trim(),
        role: role === 'client' ? 'freelancer' as const : 'client' as const,
        projects: [],
      }
      member.projects.push({ id: project.id, title: project.title, membership_status: project.membership_status })
      byName.set(key, member)
    }
    return [...byName.values()].sort((left, right) => left.name.localeCompare(right.name))
  }, [projects, role])
  const query = search.trim().toLocaleLowerCase()
  const filteredMembers = members.filter((member) => !query || `${member.name} ${member.projects.map((project) => project.title).join(' ')}`.toLocaleLowerCase().includes(query))
  const activeProjects = projects.filter((project) => project.membership_status === 'accepted').length
  const pendingInvitations = projects.filter((project) => project.membership_status === 'invited').length

  return <>
    <div className="page-heading workspace-page-heading">
      <div><span className="eyebrow">WORKSPACE / PEOPLE</span><h1>Team Directory</h1><p>See the people connected to your projects and jump into a collaboration.</p></div>
      <span className="directory-member-count">{members.length} collaborator{members.length === 1 ? '' : 's'}</span>
    </div>
    <div className="workspace-summary-row">
      <section className="surface workspace-summary-card"><small>COLLABORATORS</small><strong>{members.length}</strong><span>People connected to your workspace</span></section>
      <section className="surface workspace-summary-card"><small>ACTIVE PROJECTS</small><strong>{activeProjects}</strong><span>Accepted collaborations</span></section>
      <section className="surface workspace-summary-card"><small>PENDING INVITATIONS</small><strong>{pendingInvitations}</strong><span>Waiting for acceptance</span></section>
    </div>
    <section className="surface directory-card">
      <div className="directory-toolbar"><div><h2>Your collaborators</h2><p>Project contacts are shown from your current workspace records.</p></div><label className="directory-search"><span aria-hidden="true">⌕</span><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search people or projects" aria-label="Search people or projects"/>{search && <button type="button" onClick={() => setSearch('')} aria-label="Clear search">×</button>}</label></div>
      {filteredMembers.length === 0 ? <div className="directory-empty"><strong>{members.length ? 'No collaborators match that search' : 'Your team will appear here'}</strong><p>{members.length ? 'Try a different name or project title.' : 'Create or accept a project invitation to start building your workspace directory.'}</p></div> : <div className="directory-list" role="list">
        {filteredMembers.map((member) => {
          const active = member.projects.filter((project) => project.membership_status === 'accepted').length
          const invited = member.projects.filter((project) => project.membership_status === 'invited').length
          return <article className="directory-member" role="listitem" key={member.name.toLocaleLowerCase()}>
            <span className="directory-avatar" aria-hidden="true">{member.name.slice(0, 1).toUpperCase()}</span>
            <div className="directory-person"><strong>{member.name}</strong><span>{member.role === 'freelancer' ? 'Freelancer' : 'Client'}</span></div>
            <div className="directory-count"><strong>{active}</strong><span>active project{active === 1 ? '' : 's'}</span></div>
            {invited > 0 && <span className="directory-invitation-pill">{invited} invitation{invited === 1 ? '' : 's'}</span>}
            <div className="directory-project-links">{member.projects.slice(0, 2).map((project) => <button type="button" key={project.id} onClick={() => onOpenProject(project.id)}>{project.title}<span aria-hidden="true">↗</span></button>)}{member.projects.length > 2 && <span>+{member.projects.length - 2} more</span>}</div>
          </article>
        })}
      </div>}
    </section>
  </>
}
