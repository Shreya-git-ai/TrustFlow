import { test, expect } from '@playwright/test'
import { apiMutation, apiUrl, login, recordUiPaymentMilestone } from './helpers.js'

test('PayPal Sandbox order, buyer approval, authorization, capture, and reconciliation', async ({ page, context }) => {
  const buyerEmail = process.env.PAYPAL_SANDBOX_BUYER_EMAIL
  const buyerPassword = process.env.PAYPAL_SANDBOX_BUYER_PASSWORD
  test.fixme(!buyerEmail || !buyerPassword, 'PayPal Sandbox buyer credentials are not configured; order and capture are intentionally not attempted.')

  await login(page, 'client')
  const projectsResponse = await context.request.get(apiUrl('/api/projects'))
  expect(projectsResponse.ok()).toBeTruthy()
  const projects = await projectsResponse.json()
  const seedProject = projects.find((project: { title: string }) => project.title === 'E2E_SEED_PROJECT_03')
  expect(seedProject?.id, 'Run the approved seed before the PayPal Sandbox test.').toBeTruthy()
  await page.getByRole('button', { name: 'Open project E2E_SEED_PROJECT_03' }).click()
  await page.getByRole('button', { name: /E2E_SEED_MILESTONE_009/ }).click()
  const details = await (await context.request.get(apiUrl(`/api/milestones/${await milestoneId(context, seedProject.id)}`))).json()
  expect(details.status).toBe('approved')
  expect(details.payment).toBeFalsy()
  await recordUiPaymentMilestone(details.id)

  const orderResponse = page.waitForResponse((response) => response.url().includes('/payment/order') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Create PayPal order' }).click()
  const orderHttp = await orderResponse
  expect(orderHttp.status()).toBe(201)
  const order = await orderHttp.json()
  expect(order.approval_url).toMatch(/^https:\/\/(www\.)?sandbox\.paypal\.com\//i)

  const buyerPagePromise = context.waitForEvent('page')
  await page.getByRole('link', { name: /Continue to PayPal/ }).click()
  const buyerPage = await buyerPagePromise
  try {
    await buyerPage.waitForLoadState('domcontentloaded', { timeout: 30_000 })
    const host = new URL(buyerPage.url()).hostname
    if (!host.includes('paypal.com') || !host.includes('sandbox')) {
      test.fixme(true, `Buyer approval did not remain on PayPal Sandbox (observed host: ${host}).`)
    }
    await buyerPage.getByLabel(/email|mobile/i).fill(buyerEmail!)
    await buyerPage.getByRole('button', { name: /log in|next/i }).click()
    await buyerPage.getByLabel(/password/i).fill(buyerPassword!)
    await buyerPage.getByRole('button', { name: /log in/i }).click()
    await buyerPage.getByRole('button', { name: /agree and continue|continue|pay now/i }).click()
    await expect(buyerPage).toHaveURL(/payment-return/)
  } catch (error) {
    const observed = error instanceof Error ? error.message.split('\n')[0].slice(0, 180) : 'unknown browser behavior'
    test.fixme(true, `PayPal buyer approval could not be automated safely; stopped before authorization or capture. Observed: ${observed}`)
  }

  await page.bringToFront()
  await page.getByRole('button', { name: 'Confirm buyer approval and authorize' }).click()
  await expect(page.getByText('authorized', { exact: false }).first()).toBeVisible()
  const captureResponse = page.waitForResponse((response) => response.url().includes('/payment/capture') && response.request().method() === 'POST')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: /Capture authorized amount/ }).click()
  const captureHttp = await captureResponse
  expect([200, 202]).toContain(captureHttp.status())
  const capture = await captureHttp.json()
  if (capture.status === 'capture_pending') {
    const paymentState = await (await context.request.get(apiUrl(`/api/milestones/${await milestoneId(context, seedProject.id)}`))).json()
    expect(paymentState.payment.status).toBe('capture_pending')
    const reconcileResponse = page.waitForResponse((response) => response.url().includes('/payment/reconcile') && response.request().method() === 'POST')
    await page.getByRole('button', { name: 'Reconcile with PayPal' }).click()
    expect((await reconcileResponse).status()).toBe(200)
  }
  const finalState = await (await context.request.get(apiUrl(`/milestones/${await milestoneId(context, seedProject.id)}`))).json()
  expect(['captured', 'capture_pending']).toContain(finalState.payment.status)
  if (finalState.payment.status === 'captured') {
    const capturedId = finalState.payment.paypal_capture_id
    const duplicate = await apiMutation(context, `/api/milestones/${await milestoneId(context, seedProject.id)}/payment/capture`, {})
    expect(duplicate.status()).toBe(200)
    const afterDuplicate = await (await context.request.get(apiUrl(`/api/milestones/${await milestoneId(context, seedProject.id)}`))).json()
    expect(afterDuplicate.payment.status).toBe('captured')
    expect(afterDuplicate.payment.paypal_capture_id).toBe(capturedId)
  }
  const audit = await context.request.get(apiUrl(`/projects/${seedProject.id}/audit`))
  const eventNames = (await audit.json()).map((row: { event_type: string }) => row.event_type)
  expect(eventNames).toContain('payment.authorized')
  if (finalState.payment.status === 'captured') expect(eventNames).toContain('payment.captured')
})

async function milestoneId(context: import('@playwright/test').BrowserContext, projectId: string) {
  const response = await context.request.get(apiUrl(`/api/projects/${projectId}`))
  const project = await response.json()
  const milestone = project.milestones.find((item: { title: string }) => item.title === 'E2E_SEED_MILESTONE_009')
  if (!milestone?.id) throw new Error('Seeded PayPal milestone is missing.')
  return milestone.id as string
}
