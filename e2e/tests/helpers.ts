import { expect, type BrowserContext, type Page } from '@playwright/test'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

export const credentials = {
  client: { email: required('CLIENT_EMAIL'), password: required('CLIENT_PASSWORD') },
  freelancer: { email: required('FREELANCER_EMAIL'), password: required('FREELANCER_PASSWORD') },
}

function required(name: string) {
  const value = process.env[name]
  if (!value) throw new Error(`${name} must be configured for E2E tests.`)
  return value
}

export async function login(page: Page, role: 'client' | 'freelancer', password = credentials[role].password) {
  await loginAccount(page, credentials[role].email, password, role)
}

export async function loginAccount(page: Page, email: string, password: string, role: 'client' | 'freelancer') {
  await page.goto('/')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: role === 'client' ? /Good work starts with/ : /Keep your next milestone/ })).toBeVisible()
}

export async function csrf(context: BrowserContext) {
  const response = await context.request.get(apiUrl('/api/auth/me'))
  expect(response.status(), 'GET /auth/me should return the current session and CSRF token').toBe(200)
  const data = await response.json()
  if (typeof data.csrf_token !== 'string' || !data.csrf_token) throw new Error('The API did not return its documented CSRF token.')
  return data.csrf_token as string
}

export async function apiMutation(context: BrowserContext, path: string, body: unknown) {
  const token = await csrf(context)
  return context.request.post(apiUrl(path), {
    data: body,
    headers: { 'X-CSRF-Token': token },
  })
}

export function apiUrl(path: string) {
  return new URL(path, process.env.BASE_URL).toString()
}

export async function recordUiProject(projectId: string) {
  const manifestPath = resolve(process.cwd(), '.e2e-ui-manifest.json')
  const manifest = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, 'utf8')) : { version: 1, projectIds: [], paymentMilestoneIds: [] }
  if (manifest.version !== 1 || !Array.isArray(manifest.projectIds) || !Array.isArray(manifest.paymentMilestoneIds)) throw new Error('E2E UI manifest is invalid.')
  manifest.projectIds = [...new Set([...manifest.projectIds, projectId])]
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, { mode: 0o600 })
}

export async function recordUiPaymentMilestone(milestoneId: string) {
  const manifestPath = resolve(process.cwd(), '.e2e-ui-manifest.json')
  const manifest = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, 'utf8')) : { version: 1, projectIds: [], paymentMilestoneIds: [] }
  if (manifest.version !== 1 || !Array.isArray(manifest.projectIds) || !Array.isArray(manifest.paymentMilestoneIds)) throw new Error('E2E UI manifest is invalid.')
  manifest.paymentMilestoneIds = [...new Set([...manifest.paymentMilestoneIds, milestoneId])]
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, { mode: 0o600 })
}

export function uniqueTitle(label: string) {
  return `E2E_${label}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
}
