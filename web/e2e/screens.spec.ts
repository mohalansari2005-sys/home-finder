import { test } from '@playwright/test'
import { mockApi } from './fixtures'

// Saves screenshots to test-results/screens/ (gitignored) for visual review.
const dir = 'test-results/screens'

test('screens: login, feed, detail, settings', async ({ page }, info) => {
  const n = info.project.name
  await mockApi(page)
  await page.goto('/login')
  await page.screenshot({ path: `${dir}/${n}-login.png` })
  await mockApi(page, { loggedIn: true })
  await page.goto('/')
  await page.getByRole('article').first().waitFor()
  await page.screenshot({ path: `${dir}/${n}-feed.png` })
  await page.getByRole('article').first().click()
  await page.waitForTimeout(600)
  await page.screenshot({ path: `${dir}/${n}-detail.png` })
  await page.goto('/settings')
  await page.getByText('حالة النظام').waitFor()
  await page.screenshot({ path: `${dir}/${n}-settings.png` })
})

test('screens: dark feed', async ({ page }, info) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await mockApi(page, { loggedIn: true })
  await page.goto('/')
  await page.getByRole('article').first().waitFor()
  await page.screenshot({ path: `${dir}/${info.project.name}-feed-dark.png` })
})
