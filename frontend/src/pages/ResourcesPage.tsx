import type { Project, User } from '../api/assessment'

export default function ResourcesPage({
  role, projects, onOverview, onPayments, onOpenProject, onTeamDirectory,
}: {
  role: User['role']; projects: Project[]; onOverview: () => void; onPayments: () => void
  onOpenProject: (id: string) => void; onTeamDirectory: () => void
}) {
  const firstProject = projects.find((project) => project.membership_status === 'accepted') || projects[0]
  return <>
    <div className="page-heading workspace-page-heading resources-page-heading">
      <div><span className="eyebrow">WORKSPACE / RESOURCES</span><h1>Resources</h1><p>Guides for setting expectations, reviewing evidence, and keeping project payments clear.</p></div>
    </div>
    <section className="resources-hero">
      <div className="resources-hero-copy">
        <span className="resources-hero-kicker">THE TRUSTFLOW PLAYBOOK</span>
        <h2>Good collaboration starts with a shared plan.</h2>
        <p>Keep scope, milestones, evidence, and payment decisions together from the first invitation to the final approval.</p>
        <div className="resources-hero-actions">
          <button type="button" className="resources-hero-primary" onClick={onOverview}>Open your workspace <span aria-hidden="true">→</span></button>
          <button type="button" className="resources-hero-secondary" onClick={onPayments}>Explore payment records</button>
        </div>
      </div>
      <div className="resources-hero-aside" aria-label="Collaboration workflow">
        <span className="resources-orbit orbit-one">01</span><span className="resources-orbit orbit-two">02</span><span className="resources-orbit orbit-three">03</span>
        <div className="resources-flow-card"><i>✓</i><span><strong>One clear workflow</strong><small>Agree · Submit · Review · Decide</small></span></div>
      </div>
    </section>
    <div className="resources-card-grid">
      <article className="surface resource-card resource-card-feature">
        <span className="resource-category category-purple">START HERE</span><span className="resource-icon purple" aria-hidden="true">↗</span>
        <h2>Set up the project together</h2><p>{role === 'client' ? 'Describe the scope, invite a freelancer by their registered TrustFlow email, and agree on measurable milestones.' : 'Review the project scope and milestone criteria before accepting an invitation.'}</p>
        <button type="button" className="resource-link" onClick={onOverview}>Go to projects <span aria-hidden="true">→</span></button>
      </article>
      <article className="surface resource-card">
        <span className="resource-category category-blue">MILESTONES</span><span className="resource-icon green" aria-hidden="true">◇</span>
        <h2>Keep proof with the work</h2><p>Submit a description, links, or supported attachments to the milestone. Reviews stay connected to the agreed criteria.</p>
        <button type="button" className="resource-link" disabled={!firstProject} onClick={() => firstProject && onOpenProject(firstProject.id)}>{firstProject ? 'Open a project' : 'Create or accept a project'} <span aria-hidden="true">→</span></button>
      </article>
      <article className="surface resource-card">
        <span className="resource-category category-amber">PAYMENTS</span><span className="resource-icon amber" aria-hidden="true">$</span>
        <h2>Follow each payment step</h2><p>Track PayPal order, approval, authorization, capture, and refund activity from the related milestone.</p>
        <button type="button" className="resource-link" onClick={onPayments}>View payment records <span aria-hidden="true">→</span></button>
      </article>
      <article className="surface resource-card">
        <span className="resource-category category-green">YOUR TEAM</span><span className="resource-icon purple" aria-hidden="true">◎</span>
        <h2>Find your collaborators</h2><p>See the people attached to your projects, check invitation state, and jump back into their shared work.</p>
        <button type="button" className="resource-link" onClick={onTeamDirectory}>Open team directory <span aria-hidden="true">→</span></button>
      </article>
    </div>
    <section className="surface resources-principles">
      <div className="resources-principles-heading"><span className="eyebrow">KEEP IT CLEAR</span><h2>Built around transparent decisions</h2></div>
      <div className="resources-principle"><i className="principle-dot violet"/><div><strong>Evidence stays in context</strong><p>Reference links are stored for context; the assessor does not open them.</p></div></div>
      <div className="resources-principle"><i className="principle-dot amber"/><div><strong>Reviews guide the next step</strong><p>Assessments are advisory. Clients make the final approval or revision decision.</p></div></div>
      <div className="resources-principle"><i className="principle-dot green"/><div><strong>Payments follow the workflow</strong><p>PayPal transaction states remain visible alongside each project milestone.</p></div></div>
    </section>
  </>
}
