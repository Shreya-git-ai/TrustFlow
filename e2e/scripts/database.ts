import 'dotenv/config'
import { Pool, type PoolClient } from 'pg'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

export const manifestPath = resolve(process.cwd(), '.e2e-seed-manifest.json')
export const uiManifestPath = resolve(process.cwd(), '.e2e-ui-manifest.json')

function csv(name: string): string[] {
  return (process.env[name] || '').split(',').map((value) => value.trim().toLowerCase()).filter(Boolean)
}

export function requireSeedGate() {
  if (process.env.E2E_ALLOW_SEED !== 'true') {
    throw new Error('Database writes are disabled. Set E2E_ALLOW_SEED=true only for an approved E2E database.')
  }
}

export function databasePool() {
  const connectionString = process.env.DATABASE_URL
  if (!connectionString) throw new Error('DATABASE_URL is not configured.')
  return new Pool({ connectionString, connectionTimeoutMillis: 10_000, application_name: 'trustflow-e2e' })
}

export async function verifyTarget(client: PoolClient) {
  const databaseUrl = new URL(process.env.DATABASE_URL || '')
  const host = databaseUrl.hostname.toLowerCase()
  const identity = await client.query('SELECT current_database() AS database_name, current_user AS database_user')
  const databaseName = String(identity.rows[0]?.database_name || '').toLowerCase()
  const databaseUser = String(identity.rows[0]?.database_user || '').toLowerCase()
  const hostAllowlist = csv('E2E_DATABASE_HOST_ALLOWLIST')
  const nameAllowlist = csv('E2E_DATABASE_NAME_ALLOWLIST')
  const userAllowlist = csv('E2E_DATABASE_USER_ALLOWLIST')

  if (!hostAllowlist.length || !hostAllowlist.includes(host)) {
    throw new Error('Database host is not on E2E_DATABASE_HOST_ALLOWLIST; refusing to continue.')
  }
  if (!nameAllowlist.length || !nameAllowlist.includes(databaseName)) {
    throw new Error('Connected database is not on E2E_DATABASE_NAME_ALLOWLIST; refusing to continue.')
  }
  if (!userAllowlist.length || !userAllowlist.includes(databaseUser)) {
    throw new Error('Connected database user is not on E2E_DATABASE_USER_ALLOWLIST; refusing to continue.')
  }
  if (/(^|[._-])(prod|production|primary)([._-]|$)/i.test(`${host}.${databaseName}`)
      && process.env.E2E_ALLOW_PRODUCTION_DATABASE !== 'true') {
    throw new Error('Target looks production-related. Refusing without E2E_ALLOW_PRODUCTION_DATABASE=true.')
  }
  return { host, databaseName, databaseUser }
}

export async function connectAndVerify() {
  const pool = databasePool()
  try {
    const client = await pool.connect()
    try {
      const target = await verifyTarget(client)
      return { pool, client, target }
    } catch (error) {
      client.release()
      throw error
    }
  } catch (error) {
    await pool.end()
    if (error instanceof Error && error.message.startsWith('Database ')) throw error
    throw new Error(`Database connection or identity check failed (${error instanceof Error ? error.name : 'unknown error'}). Check the connection and allowlists; no connection details were printed.`)
  }
}

export function readManifest() {
  if (!existsSync(manifestPath)) throw new Error('Seed manifest is missing; cleanup and verification require the manifest created by seed.ts.')
  const data = JSON.parse(readFileSync(manifestPath, 'utf8'))
  if (data.version !== 1 || !Array.isArray(data.projectIds) || !Array.isArray(data.milestoneIds)) {
    throw new Error('Seed manifest format is invalid; refusing database operations.')
  }
  for (const key of ['projectIds', 'milestoneIds', 'evidenceIds', 'reportIds', 'decisionIds', 'paymentIds', 'auditIds']) {
    if (!Array.isArray(data[key]) || data[key].some((id: unknown) => typeof id !== 'string')) {
      throw new Error('Seed manifest ID list is invalid; refusing database operations.')
    }
  }
  return data as {
    version: number
    databaseHost: string
    databaseName: string
    clientId: string
    freelancerId: string
    projectIds: string[]
    milestoneIds: string[]
    evidenceIds: string[]
    reportIds: string[]
    decisionIds: string[]
    paymentIds: string[]
    auditIds: string[]
  }
}

export function readUiManifest(): { version: number; projectIds: string[]; paymentMilestoneIds: string[] } {
  if (!existsSync(uiManifestPath)) return { version: 1, projectIds: [], paymentMilestoneIds: [] }
  const data = JSON.parse(readFileSync(uiManifestPath, 'utf8'))
  if (data.version !== 1 || !Array.isArray(data.projectIds) || data.projectIds.some((id: unknown) => typeof id !== 'string')
      || (data.paymentMilestoneIds !== undefined && (!Array.isArray(data.paymentMilestoneIds) || data.paymentMilestoneIds.some((id: unknown) => typeof id !== 'string')))) {
    throw new Error('E2E UI manifest format is invalid; refusing database operations.')
  }
  return { ...data, paymentMilestoneIds: data.paymentMilestoneIds || [] } as { version: number; projectIds: string[]; paymentMilestoneIds: string[] }
}

export function assertManifestTarget(manifest: ReturnType<typeof readManifest>, target: { host: string; databaseName: string }) {
  if (manifest.databaseHost !== target.host || manifest.databaseName.toLowerCase() !== target.databaseName.toLowerCase()) {
    throw new Error('Connected database does not match the seed manifest target; refusing to continue.')
  }
}
