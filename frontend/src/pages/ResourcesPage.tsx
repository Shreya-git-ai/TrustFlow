import type { Project, User } from '../api/assessment'

export default function ResourcesPage({
  role, projects, onOverview, onPayments, onOpenProject,
}: {
  role: User['role']; projects: Project[]; onOverview: () => void; onPayments: () => void
  onOpenProject: (id: string) => void
}) {
  const firstProject = projects.find((project) => project.membership_status === 'accepted') || projects[0]
  return <>
    <div className="page-heading workspace-page-heading"><div><span className="eyebrow">WORKSPACE / RESOURCES</span><h1>Resources</h1><p>Practical guidance for keeping agreements, evidence, decisions, and payments connected.</p></div></div>
    <div className="resource-grid">
      <article className="surface resource-card"><span className="resource-icon purple">01</span><span className="eyebrow">START A PROJECT</span><h2>Agree on the work first</h2><p>Write a clear project scope, invite the other person by their TrustFlow account email, then define each milestone with measurable acceptance criteria.</p><button type="button" className="text-button" onClick={onOverview}>{role === 'client' ? 'Go to your workspace →' : 'Go to your projects →'}</button></article>
      <article className="surface resource-card"><span className="resource-icon green">02</span><span className="eyebrow">SUBMIT AND REVIEW</span><h2>Keep proof tied to a milestone</h2><p>Freelancers can submit a description, reference links, and a supported attachment. Clients can request an assessment and make the final milestone decision.</p><button type="button" className="text-button" disabled={!firstProject} onClick={() => firstProject && onOpenProject(firstProject.id)}>{firstProject ? 'Open a project →' : 'Create or accept a project first'}</button></article>
      <article className="surface resource-card"><span className="resource-icon amber">03</span><span className="eyebrow">PAYMENT WORKFLOW</span><h2>Follow the PayPal status</h2><p>Orders, buyer approval, authorization, capture, and reconciliation are tracked on the milestone. TrustFlow does not provide legal escrow.</p><button type="button" className="text-button" onClick={onPayments}>Open payment overview →</button></article>
    </div>
    <section className="surface resource-guidance"><div className="section-head"><div><span className="eyebrow">ASSESSMENT LIMITS</span><h2>What evidence review does</h2><p>TrustFlow keeps the review tied to the agreed criteria and the content submitted in the workspace.</p></div></div><div className="resource-facts"><div><span>Text</span><p>Submitted descriptions and evidence excerpts can be considered against milestone criteria.</p></div><div><span>Links</span><p>Reference URLs are stored for context; the assessor does not open them.</p></div><div><span>Attachments</span><p>Files are stored privately and can be downloaded by project members; file contents are not extracted for assessment.</p></div><div><span>Decisions</span><p>Assessment is advisory. The client remains responsible for approval, revisions, and payment actions.</p></div></div></section>
  </>
}
