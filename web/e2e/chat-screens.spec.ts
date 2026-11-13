import { test, type Page } from '@playwright/test'
import { mockApi } from './fixtures'

// Saves screenshots to test-results/screens/ (gitignored) for visual review of the chat and the M3 card states.
const dir = 'test-results/screens'
const drop = { from: 1_600_000, to: 1_500_001, at: '2026-11-10T00:00:00Z' }

async function chatShot(page: Page, name: string, project: string) {
  await page.goto(project === 'phone' ? '/assistant' : '/')
  if (project === 'tablet') {
    await page.screenshot({ path: `${dir}/${name}-fab.png` })
    await page.getByRole('button', { name: 'اسأل المساعد' }).click()
  }
  await page.screenshot({ path: `${dir}/${name}-empty.png` })
  const box = page.getByRole('textbox', { name: 'رسالتك' })
  await box.fill('غيّر الميزانية')
  await box.press('Enter')
  await page.getByText('حدّثت الميزانية.').waitFor()
  await box.fill('وش عندك؟')
  await box.press('Enter')
  await page.getByText('وجدت فيلتين مناسبتين.').waitFor()
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${dir}/${name}-answer.png` })
}

for (const scheme of ['light', 'dark'] as const) {
  test(`screens: chat ${scheme}`, async ({ page }, info) => {
    await page.emulateMedia({ colorScheme: scheme })
    await mockApi(page, { loggedIn: true, cardExtras: { 1: { price_drop: drop, family_status: 'bookmarked' }, 2: { status: 'removed', family_status: 'bookmarked' } } })
    await chatShot(page, `${info.project.name}-chat-${scheme}`, info.project.name)
  })

  test(`screens: feed with drop and removed ${scheme}`, async ({ page }, info) => {
    await page.emulateMedia({ colorScheme: scheme })
    await mockApi(page, { loggedIn: true, cardExtras: { 1: { price_drop: drop }, 2: { status: 'removed', family_status: 'bookmarked' } } })
    await page.goto('/')
    await page.getByRole('article').first().waitFor()
    await page.screenshot({ path: `${dir}/${info.project.name}-feed-m3-${scheme}.png` })
  })
}
