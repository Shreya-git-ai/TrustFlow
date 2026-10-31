import 'dotenv/config'
import { renameSync, writeFileSync } from 'node:fs'
import type { PoolClient } from 'pg'
import { manifestPath, assertManifestTarget, connectAndVerify, readManifest, requireSeedGate } from './database.ts'

const E2E = 'E2E_SEED_'
type SeedIds = { projectIds: string[]; milestoneIds: string[]; evidenceIds: string[]; reportIds: string[]; decisionIds: string[]; paymentIds: string[]; auditIds: string[] }

async function main() {
  requireSeedGate()
  const clientEmail = process.env.CLIENT_EMAIL?.trim().toLowerCase()
  const freelancerEmail = process.env.FREELANCER_EMAIL?.trim().toLowerCase()
  if (!clientEmail || !freelancerEmail || clientEmail === freelancerEmail) {
    throw new Error('Set distinct CLIENT_EMAIL and FREELANCER_EMAIL values for the existing test accounts.')
  }

  const { pool, client, target } = await connectAndVerify()
  const ids: SeedIds = { projectIds: [], milestoneIds: [], evidenceIds: [], reportIds: [], decisionIds: [], paymentIds: [], auditIds: [] }
  try {
    let prior: ReturnType<typeof readManifest> | undefined
    try {
      prior = readManifest()
      assertManifestTarget(prior, target)
    } catch (error) {
      if (error instanceof Error && !error.message.startsWith('Seed manifest is missing')) throw error
    }
    const priorIds: SeedIds = prior || { projectIds: [], milestoneIds: [], evidenceIds: [], reportIds: [], decisionIds: [], paymentIds: [], auditIds: [] }
    const owned = (row: any, type: keyof typeof priorIds) => {
      if (row && !priorIds[type].includes(String(row.id))) {
        throw new Error(`Found an E2E marker row not recorded by this seed manifest (${type}); refusing to reuse or clean it.`)
      }
      return row
    }
    await client.query('BEGIN')
    const users = await client.query(
      `SELECT id, email, role FROM users WHERE lower(email) = ANY($1::text[]) ORDER BY lower(email)`,
      [[clientEmail, freelancerEmail]],
    )
    const clientUser = users.rows.find((row) => row.role === 'client' && String(row.email).toLowerCase() === clientEmail)
    const freelancerUser = users.rows.find((row) => row.role === 'freelancer' && String(row.email).toLowerCase() === freelancerEmail)
    if (!clientUser || !freelancerUser) throw new Error('The configured client/freelancer accounts were not found with the expected roles.')

    for (let p = 1; p <= 30; p += 1) {
      const projectTitle = `${E2E}PROJECT_${String(p).padStart(2, '0')}`
      const existingProject = await client.query(
        'SELECT id FROM projects WHERE client_id = $1 AND freelancer_id = $2 AND title = $3',
        [clientUser.id, freelancerUser.id, projectTitle],
      )
      const project = owned(existingProject.rows[0], 'projectIds') || (await client.query(
        `INSERT INTO projects(client_id, freelancer_id, title, description, currency, status, membership_status, membership_accepted_at)
         VALUES ($1, $2, $3, $4, 'USD', 'active', 'accepted', NOW()) RETURNING id`,
        [clientUser.id, freelancerUser.id, projectTitle, 'Synthetic E2E collaboration for workflow and database verification.'],
      )).rows[0]
      const projectId = String(project.id)
      ids.projectIds.push(projectId)

      for (let m = 1; m <= 4; m += 1) {
        const n = (p - 1) * 4 + m
        const milestoneTitle = `${E2E}MILESTONE_${String(n).padStart(3, '0')}`
        const existingMilestone = await client.query('SELECT id FROM milestones WHERE project_id = $1 AND title = $2', [projectId, milestoneTitle])
        const milestone = owned(existingMilestone.rows[0], 'milestoneIds') || (await client.query(
          `INSERT INTO milestones(project_id, title, acceptance_criteria, amount, currency, status)
           VALUES ($1, $2, $3::jsonb, $4, 'USD', 'submitted') RETURNING id`,
          [projectId, milestoneTitle, JSON.stringify(['E2E deliverable is present', 'E2E review notes are included']), (100 + n).toFixed(2)],
        )).rows[0]
        const milestoneId = String(milestone.id)
        ids.milestoneIds.push(milestoneId)

        let evidence = owned((await client.query('SELECT id FROM evidence WHERE milestone_id = $1 AND evidence_revision = 1', [milestoneId])).rows[0], 'evidenceIds')
        if (!evidence) evidence = (await client.query(
          `INSERT INTO evidence(milestone_id, evidence_revision, description, evidence_text, evidence_links)
           VALUES ($1, 1, $2, $2, '[]'::jsonb) RETURNING id`,
          [milestoneId, `${E2E} synthetic evidence for milestone ${n}; deliverable and review notes are present.`],
        )).rows[0]
        ids.evidenceIds.push(String(evidence.id))
        await client.query("UPDATE milestones SET evidence_revision = GREATEST(evidence_revision, 1), status = 'submitted' WHERE id = $1", [milestoneId])

        const outcomes = ['ok', 'empty_evidence', 'invalid_output', 'provider_error']
        const outcome = outcomes[(n - 1) % outcomes.length]
        const allMet = outcome === 'ok' && n % 8 === 1
        let report = owned((await client.query(
          'SELECT id FROM assessment_reports WHERE milestone_id = $1 AND evidence_revision = 1 AND report_version = $2',
          [milestoneId, `${E2E}REPORT_V1`],
        )).rows[0], 'reportIds')
        if (!report) report = (await client.query(
          `INSERT INTO assessment_reports(milestone_id, evidence_revision, report_version, prompt_version, model, outcome, all_met, is_stale, result_json)
           VALUES ($1, 1, $2, 'e2e-seed', 'synthetic', $3, $4, FALSE, $5::jsonb) RETURNING id`,
          [milestoneId, `${E2E}REPORT_V1`, outcome, allMet, JSON.stringify({ synthetic: true, outcome, all_met: allMet })],
        )).rows[0]
        const reportId = String(report.id)
        ids.reportIds.push(reportId)
        if (outcome === 'ok') {
          await client.query(
            `INSERT INTO assessment_findings(report_id, criterion_id, status, explanation, quote)
             VALUES ($1, 1, $2, $3, $4) ON CONFLICT (report_id, criterion_id) DO NOTHING`,
            [reportId, allMet ? 'met' : 'partially_met', 'Synthetic seeded finding for verification.', allMet ? `${E2E} synthetic evidence` : null],
          )
          await client.query(
            `INSERT INTO assessment_findings(report_id, criterion_id, status, explanation, quote)
             VALUES ($1, 2, $2, 'Synthetic seeded finding for verification.', $3) ON CONFLICT (report_id, criterion_id) DO NOTHING`,
            [reportId, allMet ? 'met' : 'unable_to_verify', allMet ? `${E2E} synthetic evidence` : null],
          )
        }

        if (allMet) {
          const existingDecision = owned((await client.query('SELECT id FROM milestone_decisions WHERE milestone_id = $1 AND note = $2', [milestoneId, `${E2E} seeded approval`])).rows[0], 'decisionIds')
          const decision = existingDecision || (await client.query(
            `INSERT INTO milestone_decisions(milestone_id, actor_id, decision, evidence_revision, assessment_report_id, note)
             VALUES ($1, $2, 'approved', 1, $3, $4) RETURNING id`,
            [milestoneId, clientUser.id, reportId, `${E2E} seeded approval`],
          )).rows[0]
          ids.decisionIds.push(String(decision.id))
          const captured = n % 16 === 1
          await client.query(
            `UPDATE milestones SET status = $2, approved_evidence_revision = 1, approved_assessment_id = $3, approved_at = NOW() WHERE id = $1`,
            [milestoneId, captured ? 'paid' : 'approved', reportId],
          )
          if (captured) {
            const payment = await upsertPayment(client, milestoneId, clientUser.id, n, 'captured', priorIds.paymentIds)
            ids.paymentIds.push(payment)
          } else if (n % 32 === 25) {
            const payment = await upsertPayment(client, milestoneId, clientUser.id, n, 'authorized', priorIds.paymentIds)
            ids.paymentIds.push(payment)
          }
        } else if (n % 4 === 0) {
          const payment = await upsertPayment(client, milestoneId, clientUser.id, n, 'failed', priorIds.paymentIds)
          ids.paymentIds.push(payment)
        } else if (n % 10 === 0) {
          const payment = await upsertPayment(client, milestoneId, clientUser.id, n, 'created', priorIds.paymentIds)
          ids.paymentIds.push(payment)
        }

        const audit = owned((await client.query(
          `SELECT id FROM audit_events WHERE milestone_id = $1 AND event_type = 'e2e.seeded'
             AND details->>'seed_key' = $2`, [milestoneId, `${E2E}${n}`],
        )).rows[0], 'auditIds') || (await client.query(
          `INSERT INTO audit_events(project_id, milestone_id, event_type, actor_type, actor_id, details)
           VALUES ($1, $2, 'e2e.seeded', 'system', NULL, $3::jsonb) RETURNING id`,
          [projectId, milestoneId, JSON.stringify({ seed_key: `${E2E}${n}`, synthetic: true })],
        )).rows[0]
        ids.auditIds.push(String(audit.id))
      }
    }

    const manifest = {
      version: 1, databaseHost: target.host, databaseName: target.databaseName,
      clientId: String(clientUser.id), freelancerId: String(freelancerUser.id), ...ids,
    }
    const merged = prior ? Object.fromEntries(Object.entries(ids).map(([key, values]) => [key, [...new Set([...(prior![key as keyof typeof prior] as string[]), ...values])]])) : ids
    const tempManifest = `${manifestPath}.tmp`
    writeFileSync(tempManifest, `${JSON.stringify({ ...manifest, ...merged }, null, 2)}\n`, { mode: 0o600 })
    renameSync(tempManifest, manifestPath)
    await client.query('COMMIT')
    console.log(`Seed complete: ${ids.projectIds.length} projects, ${ids.milestoneIds.length} milestones, ${ids.evidenceIds.length} evidence records, ${ids.reportIds.length} reports, ${ids.paymentIds.length} payments, ${ids.auditIds.length} audit entries.`)
  } catch (error) {
    await client.query('ROLLBACK').catch(() => undefined)
    throw error
  } finally {
    client.release()
    await pool.end()
  }
}

async function upsertPayment(client: PoolClient, milestoneId: string, clientId: string, n: number, status: string, ownedIds: string[]) {
  const existing = (await client.query('SELECT id FROM payments WHERE milestone_id = $1', [milestoneId])).rows[0]
  if (existing) {
    if (!ownedIds.includes(String(existing.id))) throw new Error('Payment already exists on a seed milestone without a recorded E2E payment ID; refusing to reuse it.')
    return String(existing.id)
  }
  const amount = (100 + n).toFixed(2)
  const row = (await client.query(
    `INSERT INTO payments(milestone_id, created_by, amount, currency, status, create_request_id, authorize_request_id,
       paypal_order_id, paypal_authorization_id, paypal_capture_id)
     VALUES ($1, $2, $3, 'USD', $4, $5, $6, $7, $8, $9) RETURNING id`,
    [milestoneId, clientId, amount, status, `${E2E}create_${n}`, `${E2E}auth_${n}`,
      status === 'created' ? null : `${E2E}order_${n}`,
      status === 'authorized' || status === 'captured' ? `${E2E}authorization_${n}` : null,
      status === 'captured' ? `${E2E}capture_${n}` : null],
  )).rows[0]
  return String(row.id)
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : 'Seed failed.')
  process.exitCode = 1
})
