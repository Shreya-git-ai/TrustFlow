import 'dotenv/config'
import { existsSync, unlinkSync } from 'node:fs'
import { assertManifestTarget, connectAndVerify, manifestPath, readManifest, readUiManifest, requireSeedGate, uiManifestPath } from './database.ts'

async function main() {
  requireSeedGate()
  const manifest = existsSync(manifestPath) ? readManifest() : undefined
  const uiManifest = readUiManifest()
  if (!manifest && uiManifest.projectIds.length === 0) throw new Error('No E2E seed or UI project manifest exists; refusing cleanup.')
  const { pool, client, target } = await connectAndVerify()
  try {
    if (manifest) assertManifestTarget(manifest, target)
    const uiProjects = uiManifest.projectIds.length ? await client.query(
      'SELECT id, title FROM projects WHERE id = ANY($1::uuid[])', [uiManifest.projectIds],
    ) : { rows: [] as { id: string; title: string }[], rowCount: 0 }
    if ((uiProjects.rowCount ?? uiProjects.rows.length) !== uiManifest.projectIds.length || uiProjects.rows.some((row) => !row.title.startsWith('E2E_'))) {
      throw new Error('An E2E UI project is missing or no longer has its E2E title marker; refusing cleanup.')
    }
    await client.query('BEGIN')
    if (uiManifest.paymentMilestoneIds.length) {
      const paymentRows = await client.query('SELECT id, paypal_order_id FROM payments WHERE milestone_id = ANY($1::uuid[])', [uiManifest.paymentMilestoneIds])
      const paymentIds = paymentRows.rows.map((row) => String(row.id))
      const orderIds = paymentRows.rows.map((row) => row.paypal_order_id).filter(Boolean)
      if (paymentIds.length) {
        await client.query('DELETE FROM audit_events WHERE payment_id = ANY($1::uuid[])', [paymentIds])
        await client.query("DELETE FROM integration_outbox WHERE payload->>'payment_id' = ANY($1::text[]) OR payload->>'order_id' = ANY($2::text[])", [paymentIds, orderIds])
        await client.query('DELETE FROM payment_refunds WHERE payment_id = ANY($1::uuid[])', [paymentIds])
        await client.query('DELETE FROM refund_proposals WHERE payment_id = ANY($1::uuid[])', [paymentIds])
        await client.query('DELETE FROM payments WHERE id = ANY($1::uuid[])', [paymentIds])
      }
    }
    if (manifest) {
      await client.query('DELETE FROM audit_events WHERE id = ANY($1::bigint[])', [manifest.auditIds])
      await client.query('DELETE FROM milestone_decisions WHERE id = ANY($1::uuid[])', [manifest.decisionIds])
      await client.query('DELETE FROM payments WHERE id = ANY($1::uuid[])', [manifest.paymentIds])
      await client.query('UPDATE milestones SET approved_assessment_id = NULL WHERE id = ANY($1::uuid[])', [manifest.milestoneIds])
      await client.query('DELETE FROM assessment_findings WHERE report_id = ANY($1::uuid[])', [manifest.reportIds])
      await client.query('DELETE FROM assessment_reports WHERE id = ANY($1::uuid[])', [manifest.reportIds])
      await client.query('DELETE FROM evidence WHERE id = ANY($1::uuid[])', [manifest.evidenceIds])
      await client.query('DELETE FROM milestones WHERE id = ANY($1::uuid[])', [manifest.milestoneIds])
      await client.query('DELETE FROM projects WHERE id = ANY($1::uuid[])', [manifest.projectIds])
    }
    if (uiManifest.projectIds.length) {
      const milestones = await client.query('SELECT id FROM milestones WHERE project_id = ANY($1::uuid[])', [uiManifest.projectIds])
      const milestoneIds = milestones.rows.map((row) => row.id)
      const reports = milestoneIds.length ? await client.query('SELECT id FROM assessment_reports WHERE milestone_id = ANY($1::uuid[])', [milestoneIds]) : { rows: [] }
      const reportIds = reports.rows.map((row) => row.id)
      const payments = milestoneIds.length ? await client.query('SELECT id FROM payments WHERE milestone_id = ANY($1::uuid[])', [milestoneIds]) : { rows: [] }
      const paymentIds = payments.rows.map((row) => row.id)
      if (paymentIds.length) {
        await client.query('DELETE FROM payment_refunds WHERE payment_id = ANY($1::uuid[])', [paymentIds])
        await client.query('DELETE FROM refund_proposals WHERE payment_id = ANY($1::uuid[])', [paymentIds])
        await client.query('DELETE FROM payments WHERE id = ANY($1::uuid[])', [paymentIds])
      }
      if (milestoneIds.length) {
        await client.query('DELETE FROM milestone_decisions WHERE milestone_id = ANY($1::uuid[])', [milestoneIds])
        await client.query('UPDATE milestones SET approved_assessment_id = NULL WHERE id = ANY($1::uuid[])', [milestoneIds])
      }
      if (reportIds.length) {
        await client.query('DELETE FROM assessment_findings WHERE report_id = ANY($1::uuid[])', [reportIds])
        await client.query('DELETE FROM assessment_reports WHERE id = ANY($1::uuid[])', [reportIds])
      }
      if (milestoneIds.length) await client.query('DELETE FROM evidence WHERE milestone_id = ANY($1::uuid[])', [milestoneIds])
      if (milestoneIds.length) await client.query('DELETE FROM milestones WHERE id = ANY($1::uuid[])', [milestoneIds])
      await client.query('DELETE FROM audit_events WHERE project_id = ANY($1::uuid[])', [uiManifest.projectIds])
      await client.query("DELETE FROM integration_outbox WHERE payload->>'project_id' = ANY($1::text[])", [uiManifest.projectIds])
      await client.query('DELETE FROM projects WHERE id = ANY($1::uuid[])', [uiManifest.projectIds])
    }
    await client.query('COMMIT')
    if (manifest && existsSync(manifestPath)) unlinkSync(manifestPath)
    if (existsSync(uiManifestPath)) unlinkSync(uiManifestPath)
    console.log(`Cleanup complete: removed ${manifest?.projectIds.length || 0} seeded projects and ${uiProjects.rows.length} UI-test projects with their related records. Test accounts were preserved.`)
  } catch (error) {
    await client.query('ROLLBACK').catch(() => undefined)
    throw error
  } finally {
    client.release()
    await pool.end()
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : 'Cleanup failed.')
  process.exitCode = 1
})
