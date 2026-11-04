import { test, expect } from '@playwright/test'
import { login } from './helpers.js'

test('client can navigate the main workspace sections', async ({ page }) => {
  await login(page, 'client')

  await page.getByRole('button', { name: 'Payments' }).click()
  await expect(page.getByRole('heading', { name: 'Payments', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Milestone payments' })).toBeVisible()
  await page.getByRole('button', { name: 'Insights' }).click()
  await expect(page.getByRole('heading', { name: 'Insights', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Resources' }).click()
  await expect(page.getByRole('heading', { name: 'Resources', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Overview' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Good work starts with')
})

test('account settings show notification preferences', async ({ page }) => {
  await login(page, 'client')
  await page.getByRole('button', { name: 'Open account settings' }).click()
  await expect(page.getByRole('heading', { name: 'Account settings' })).toBeVisible()
  await expect(page.getByText('Project updates', { exact: true })).toBeVisible()
  await expect(page.getByText('Payment alerts', { exact: true })).toBeVisible()
  await expect(page.locator('input[type="checkbox"]')).toHaveCount(2)
})

test('notification centre can mark items read or show its empty state', async ({ page }) => {
  await login(page, 'client')
  await page.getByRole('button', { name: /open notifications/i }).click()
  const dialog = page.getByRole('dialog', { name: 'Notification centre' })
  await expect(dialog).toBeVisible()
  const markRead = dialog.getByRole('button', { name: 'Mark all read' })
  if (await markRead.isEnabled()) {
    await markRead.click()
    await expect(dialog.getByRole('button', { name: 'All caught up' })).toBeDisabled()
  } else {
    await expect(dialog.getByText('You’re all caught up.')).toBeVisible()
  }
})
