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
  await page.getByText('سجل التغييرات').waitFor()
  await page.screenshot({ path: `${dir}/${n}-settings.png` })
  await page.getByLabel('أعلى سعر').fill('2000000')
  await page.getByRole('button', { name: 'حفظ الفلاتر' }).click()
  await page.getByRole('button', { name: 'عرض التفاصيل' }).first().click()
  await page.screenshot({ path: `${dir}/${n}-settings-full.png`, fullPage: true })
})

test('screens: dark feed', async ({ page }, info) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await mockApi(page, { loggedIn: true })
  await page.goto('/')
  await page.getByRole('article').first().waitFor()
  await page.screenshot({ path: `${dir}/${info.project.name}-feed-dark.png` })
})

test('screens: dark settings', async ({ page }, info) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await mockApi(page, { loggedIn: true, paused: true })
  await page.goto('/settings')
  await page.getByText('سجل التغييرات').waitFor()
  await page.screenshot({ path: `${dir}/${info.project.name}-settings-dark.png`, fullPage: true })
})
