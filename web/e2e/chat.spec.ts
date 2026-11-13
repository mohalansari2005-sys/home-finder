import { expect, test, type Page } from '@playwright/test'
import { mockApi } from './fixtures'

const panel = (page: Page) => page.locator('section[aria-label="المساعد"]')
const input = (page: Page) => page.getByRole('textbox', { name: 'رسالتك' })

/** Phone: the المساعد tab. Tablet: the floating button. Desktop: docked next to the feed. */
async function openChat(page: Page, project: string) {
  await page.goto('/')
  if (project === 'phone') {
    await page.getByTestId('bottom-tabs').getByRole('link', { name: 'المساعد' }).click()
    await expect(page).toHaveURL(/\/assistant$/)
  } else if (project === 'tablet') {
    await page.getByRole('button', { name: 'اسأل المساعد' }).click()
    await expect(page.getByRole('dialog', { name: 'المساعد' })).toBeVisible()
  } else {
    await expect(page.getByTestId('chat-dock')).toBeVisible()
    await expect(page.getByRole('article').first()).toBeVisible()
  }
  await expect(panel(page)).toBeVisible()
}

async function ask(page: Page, text: string) {
  await input(page).fill(text)
  await input(page).press('Enter')
}

test('layout per viewport; streamed answer with a listing strip; new chat clears', async ({ page }, info) => {
  await mockApi(page, { loggedIn: true })
  await openChat(page, info.project.name)
  await expect(page.getByRole('button', { name: 'وش أفضل البيوت حالياً؟' })).toBeVisible()
  await ask(page, 'وش عندك؟')
  await expect(page.getByText('وش عندك؟', { exact: true })).toBeVisible()
  await expect(panel(page).getByText('وجدت فيلتين مناسبتين.')).toBeVisible()
  const strip = panel(page).getByTestId('chat-listings')
  await expect(strip.getByRole('link')).toHaveCount(2)
  await expect(strip).toContainText('1,500,001')
  await expect(input(page)).toBeFocused()
  await page.screenshot({ path: `test-results/screens/${info.project.name}-chat.png` })
  await panel(page).getByRole('button', { name: 'محادثة جديدة' }).click()
  await expect(panel(page).getByText('وجدت فيلتين مناسبتين.')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'وش أفضل البيوت حالياً؟' })).toBeVisible()
})

test('opening a card from the strip goes to the detail for this viewport', async ({ page }, info) => {
  await mockApi(page, { loggedIn: true })
  await openChat(page, info.project.name)
  await ask(page, 'وش عندك؟')
  await panel(page).getByTestId('chat-listings').getByRole('link').first().click()
  await expect(page).toHaveURL(info.project.name === 'phone' ? /\/listing\/1$/ : /\?id=1$/)
})

test('prefs_changed shows the notice and refreshes the feed', async ({ page }, info) => {
  await mockApi(page, { loggedIn: true })
  let feedCalls = 0
  page.on('request', (r) => { if (new URL(r.url()).pathname === '/api/feed') feedCalls++ })
  await openChat(page, info.project.name)
  await page.waitForTimeout(300)
  const before = feedCalls
  await ask(page, 'غيّر الميزانية')
  await expect(panel(page).getByText('تم تحديث التفضيلات')).toBeVisible()
  await expect(panel(page).getByText('حدّثت الميزانية.')).toBeVisible()
  // the feed is only mounted (so only refetched) when it is visible next to the chat
  if (info.project.name !== 'phone') await expect.poll(() => feedCalls).toBeGreaterThan(before)
})

test('budget exhausted shows the message with no retry', async ({ page }, info) => {
  await mockApi(page, { loggedIn: true })
  await openChat(page, info.project.name)
  await ask(page, 'وصلنا الحد؟')
  const alert = panel(page).getByRole('alert')
  await expect(alert).toHaveText('تم الوصول إلى الحد الشهري لاستخدام المساعد')
  await expect(alert.getByRole('button')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'إرسال' })).toBeVisible()
})

test('no OPENAI key: friendly not-set-up message', async ({ page }, info) => {
  await mockApi(page, { loggedIn: true, chatNoKey: true })
  await openChat(page, info.project.name)
  await ask(page, 'هلا')
  await expect(panel(page).getByRole('alert')).toContainText('المساعد غير مفعّل بعد')
})

test('network failure shows retry and recovers', async ({ page }, info) => {
  await mockApi(page, { loggedIn: true, chatDropFirst: true })
  await openChat(page, info.project.name)
  await ask(page, 'وش عندك؟')
  await panel(page).getByRole('button', { name: 'إعادة المحاولة' }).click()
  await expect(panel(page).getByText('وجدت فيلتين مناسبتين.')).toBeVisible()
  await expect(panel(page).getByRole('alert')).toHaveCount(0)
})
