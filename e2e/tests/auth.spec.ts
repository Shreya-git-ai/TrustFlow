import { test, expect } from '@playwright/test'
import { apiUrl, credentials, login } from './helpers.js'

test('client can log in, log out, and no longer use the session', async ({ page, context }) => {
  await login(page, 'client')
  const current = await context.request.get(apiUrl('/api/auth/me'))
  expect(current.status()).toBe(200)

  await page.getByRole('button', { name: 'Open account menu' }).click()
  await page.getByRole('menuitem', { name: /Log out/ }).click()
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
  expect((await context.request.get(apiUrl('/api/auth/me'))).status()).toBe(401)
  expect((await context.request.get(apiUrl('/api/projects'))).status()).toBe(401)
})

test('freelancer can log in to the freelancer workspace', async ({ page, context }) => {
  await login(page, 'freelancer')
  const response = await context.request.get(apiUrl('/api/auth/me'))
  expect(response.status()).toBe(200)
  expect((await response.json()).user.role).toBe('freelancer')
})

test('invalid password is rejected without opening a session', async ({ page, context }) => {
  await page.goto('/')
  await page.getByLabel('Email', { exact: true }).fill(credentials.client.email)
  await page.locator('input[type="password"]').first().fill(`${credentials.client.password}-invalid`)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toContainText(/invalid|incorrect|sign in/i)
  expect((await context.request.get(apiUrl('/api/auth/me'))).status()).toBe(401)
})
