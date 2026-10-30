import 'dotenv/config'
import { existsSync } from 'node:fs'
import { assertManifestTarget, connectAndVerify, manifestPath, readManifest, readUiManifest } from './database.ts'

type SeedLists = Pick<ReturnType<typeof readManifest>, 'projectIds' | 'milestoneIds' | 'evidenceIds' | 'reportIds' | 'decisionIds' | 'paymentIds' | 'auditIds'>

async function main() {
  const manifest = existsSync(manifestPath) ? readManifest() : undefined
  const uiManifest = readUiManifest()
  if (!manifest && uiManifest.projectIds.length === 0) throw new Error('No E2E seed or UI test manifest exists; nothing to verify.')
  const { pool, client, target } = await connectAndVerify()
  try {
    if (manifest) assertManifestTarget(manifest, target)
    const seed: SeedLists = manifest || { projectIds: [], milestoneIds: [], evidenceIds: [], reportIds: [], decisionIds: [], paymentIds: [], auditIds: [] }
    const allProjectIds = [...new Set([...seed.projectIds, ...uiManifest.projectIds])]
    const uiProjects = uiManifest.projectIds.length ? await client.query('SELECT id, title FROM projects WHERE id = ANY($1::uuid[])', [uiManifest.projectIds]) : { rows: [], rowCount: 0 }
    const projects = await client.query('SELECT id, client_id, freelancer_id, title FROM projects WHERE id = ANY($1::uuid[])', [seed.projectIds])
    const milestones = await client.query(
      `SELECT id, project_id, evidence_revision, status, approved_assessment_id FROM milestones
       WHERE id = ANY($1::uuid[]) OR project_id = ANY($2::uuid[])`, [seed.milestoneIds, uiManifest.projectIds],
    )
    const milestoneIds = [...new Set(milestones.rows.map((row) => String(row.id)))]
    const evidence = await client.query(
      `SELECT id, milestone_id, evidence_revision FROM evidence WHERE id = ANY($1::uuid[]) OR milestone_id = ANY($2::uuid[])`,
      [seed.evidenceIds, milestoneIds],
    )
    const reports = await client.query(
      `SELECT id, milestone_id, evidence_revision, outcome, all_met, is_stale FROM assessment_reports
       WHERE id = ANY($1::uuid[]) OR milestone_id = ANY($2::uuid[])`, [seed.reportIds, milestoneIds],
    )
    const reportIds = [...new Set(reports.rows.map((row) => String(row.id)))]
    const decisions = await client.query(
      `SELECT id, milestone_id, evidence_revision, assessment_report_id FROM milestone_decisions
       WHERE id = ANY($1::uuid[]) OR milestone_id = ANY($2::uuid[])`, [seed.decisionIds, milestoneIds],
    )
    const payments = await client.query(
      `SELECT pay.id, pay.milestone_id, pay.status, pay.amount, pay.currency,
              milestone.status AS milestone_status, milestone.amount AS milestone_amount, milestone.currency AS milestone_currency
       FROM payments pay JOIN milestones milestone ON milestone.id = pay.milestone_id
       WHERE pay.id = ANY($1::uuid[]) OR pay.milestone_id = ANY($2::uuid[]) OR pay.milestone_id = ANY($3::uuid[])`,
      [seed.paymentIds, milestoneIds, uiManifest.paymentMilestoneIds],
    )
    const audits = await client.query(
      `SELECT id, project_id, milestone_id, event_type FROM audit_events WHERE id = ANY($1::bigint[]) OR project_id = ANY($2::uuid[])`,
      [seed.auditIds, allProjectIds],
    )
    const issues: string[] = []

    for (const [label, expected, actual] of [
      ['projects', seed.projectIds.length, projects.rowCount],
      ['UI projects', uiManifest.projectIds.length, uiProjects.rowCount],
      ['seeded milestones', seed.milestoneIds.length, seed.milestoneIds.filter((id) => milestones.rows.some((row) => String(row.id) === id)).length],
      ['seeded evidence', seed.evidenceIds.length, seed.evidenceIds.filter((id) => evidence.rows.some((row) => String(row.id) === id)).length],
      ['seeded assessment reports', seed.reportIds.length, seed.reportIds.filter((id) => reports.rows.some((row) => String(row.id) === id)).length],
      ['seeded decisions', seed.decisionIds.length, seed.decisionIds.filter((id) => decisions.rows.some((row) => String(row.id) === id)).length],
      ['seeded payments', seed.paymentIds.length, seed.paymentIds.filter((id) => payments.rows.some((row) => String(row.id) === id)).length],
      ['seeded audit entries', seed.auditIds.length, seed.auditIds.filter((id) => audits.rows.some((row) => String(row.id) === id)).length],
    ] as const) if (expected !== actual) issues.push(`${label}: expected ${expected}, found ${actual}`)

    const evidenceByMilestone = new Map(evidence.rows.map((row) => [String(row.milestone_id), row]))
    for (const report of reports.rows) {
      const item = evidenceByMilestone.get(String(report.milestone_id))
      if (!item || Number(item.evidence_revision) !== Number(report.evidence_revision)) {
        issues.push(`assessment ${report.id} does not reference the seeded current evidence revision`)
      }
    }
    const milestoneById = new Map(milestones.rows.map((row) => [String(row.id), row]))
    for (const payment of payments.rows) {
      const milestone = milestoneById.get(String(payment.milestone_id))
      if (!milestone || Number(payment.amount) !== Number(payment.milestone_amount)
          || payment.currency.trim() !== payment.milestone_currency.trim()) {
        issues.push(`payment ${payment.id} amount/currency does not match its milestone`)
      }
      if (payment.status === 'captured' && milestone?.status !== 'paid') issues.push(`captured payment ${payment.id} is not linked to a paid milestone`)
      if (payment.status === 'authorized' && milestone?.status !== 'approved') issues.push(`authorized payment ${payment.id} is not linked to an approved milestone`)
    }
    for (const milestoneId of uiManifest.paymentMilestoneIds) {
      if (!payments.rows.some((row) => String(row.milestone_id) === milestoneId)) {
        issues.push(`UI PayPal workflow has no persisted payment for milestone ${milestoneId}`)
      }
    }
    if (manifest) {
      for (const project of projects.rows) {
        if (String(project.client_id) !== manifest.clientId || String(project.freelancer_id) !== manifest.freelancerId
            || !project.title.startsWith('E2E_SEED_')) issues.push(`seeded project ${project.id} has an unexpected owner or title marker`)
      }
    }
    if (manifest) {
      const outcomes = new Set(reports.rows.filter((row) => seed.reportIds.includes(String(row.id))).map((row) => row.outcome))
      for (const outcome of ['ok', 'empty_evidence', 'invalid_output', 'provider_error']) {
        if (!outcomes.has(outcome)) issues.push(`seeded assessment outcome ${outcome} is missing`)
      }
      const paymentStates = new Set(payments.rows.filter((row) => seed.paymentIds.includes(String(row.id))).map((row) => row.status))
      for (const status of ['created', 'failed', 'authorized', 'captured']) {
        if (!paymentStates.has(status)) issues.push(`seeded payment state ${status} is missing`)
      }
    }
    const reportById = new Map(reports.rows.map((row) => [String(row.id), row]))
    for (const decision of decisions.rows) {
      const report = reportById.get(String(decision.assessment_report_id))
      if (!report || String(report.milestone_id) !== String(decision.milestone_id)
          || Number(report.evidence_revision) !== Number(decision.evidence_revision) || !report.all_met || report.is_stale) {
        issues.push(`decision ${decision.id} does not reference a valid passing seeded assessment`)
      }
    }
    for (const milestone of milestones.rows) {
      if (milestone.approved_assessment_id) {
        const report = reportById.get(String(milestone.approved_assessment_id))
        if (!report || String(report.milestone_id) !== String(milestone.id)
            || Number(report.evidence_revision) !== Number(milestone.evidence_revision) || !report.all_met || report.is_stale) {
          issues.push(`milestone ${milestone.id} has an invalid approval assessment reference`)
        }
      }
    }
    const milestoneSet = new Set([...seed.milestoneIds, ...milestoneIds])
    for (const payment of payments.rows) if (!milestoneSet.has(String(payment.milestone_id))) issues.push(`payment ${payment.id} is orphaned from the seed manifest`)
    const projectSet = new Set(allProjectIds)
    for (const audit of audits.rows) {
      if (audit.project_id && !projectSet.has(String(audit.project_id))) issues.push(`audit entry ${audit.id} points outside the seeded projects`)
      if (audit.milestone_id && !milestoneSet.has(String(audit.milestone_id))) issues.push(`audit entry ${audit.id} points outside the seeded milestones`)
    }

    for (const project of uiProjects.rows) if (!project.title.startsWith('E2E_')) issues.push(`UI project ${project.id} is missing the E2E marker`)
    for (const projectId of uiManifest.projectIds) {
      const events = audits.rows.filter((row) => String(row.project_id) === projectId)
      if (!events.some((row) => row.milestone_id)) issues.push(`UI project ${projectId} has no milestone audit event; inspect the UI test result`)
      const project = uiProjects.rows.find((row) => String(row.id) === projectId)
      const eventNames = new Set(events.map((row: any) => row.event_type))
      const required = project?.title.includes('WORKFLOW')
        ? ['project.created', 'milestone.created', 'evidence.submitted', 'assessment.completed', 'milestone.approved']
        : project?.title.includes('INJECTION')
          ? ['project.created', 'milestone.created', 'evidence.submitted', 'assessment.completed']
          : ['project.created']
      for (const eventName of required) if (!eventNames.has(eventName)) issues.push(`UI project ${projectId} is missing expected audit event ${eventName}`)
    }
    const statusSummary = payments.rows.reduce((summary, row) => {
      summary[row.status] = (summary[row.status] || 0) + 1
      return summary
    }, {} as Record<string, number>)
    if (issues.length) {
      console.error(`Verification failed with ${issues.length} issue(s):`)
      for (const issue of issues) console.error(`- ${issue}`)
      process.exitCode = 1
      return
    }
    console.log(`Verification passed: ${allProjectIds.length} E2E projects, ${milestones.rowCount} milestones, ${evidence.rowCount} evidence records, ${reports.rowCount} assessments, ${decisions.rowCount} decisions, ${payments.rowCount} payments, ${audits.rowCount} audit entries.`)
    console.log(`Payment states: ${JSON.stringify(statusSummary)}`)
    console.log(`UI action verification: ${uiManifest.projectIds.length} recorded UI project(s) and related database actions checked.`)
  } finally {
    client.release()
    await pool.end()
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : 'Verification failed.')
  process.exitCode = 1
})
