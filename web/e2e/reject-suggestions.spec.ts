import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

const card2 = (page: import('@playwright/test').Page) => page.getByRole('article').filter({ hasText: 'فيلا 2' })

test('reject opens the reason sheet; submit removes the card and offers undo', async ({ page }) => {
  const api = await mockApi(page, { loggedIn: true, noSuggestions: true })
  await page.goto('/')
  await card2(page).getByRole('button', { name: 'استبعاد' }).click()
  const sheet = page.getByRole('dialog')
  await expect(sheet).toBeVisible()
  await sheet.getByRole('radio', { name: 'الشارع ضيق' }).click()
  await sheet.getByLabel('ملاحظة (اختياري)').fill('الشارع ضيق جدا')
  await sheet.getByRole('button', { name: 'استبعاد' }).click()
  await expect(card2(page)).toHaveCount(0)
  await expect(page.getByText('تم الاستبعاد')).toBeVisible()
  expect(api.reacts.at(-1)).toMatchObject({ id: 2, kind: 'reject', reason_code: 'narrow_street', note: 'الشارع ضيق جدا' })
  await page.getByRole('button', { name: 'تراجع' }).click()
  await expect.poll(() => api.reacts.at(-1)?.kind).toBe('unreject')
  await expect(card2(page)).toBeVisible()
})

test('cancelling the sheet keeps the listing', async ({ page }) => {
  const api = await mockApi(page, { loggedIn: true, noSuggestions: true })
  await page.goto('/')
  await card2(page).getByRole('button', { name: 'استبعاد' }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(card2(page)).toBeVisible()
  expect(api.reacts).toHaveLength(0)
})

test('suggestion banner: apply and dismiss', async ({ page }) => {
  const api = await mockApi(page, { loggedIn: true })
  await page.goto('/')
  const banner = page.getByRole('region', { name: 'اقتراح' })
  await expect(banner).toContainText('رفضتم 5 عقارات لأنها قديمة')
  await banner.getByRole('button', { name: 'تطبيق' }).click()
  await expect(banner).toHaveCount(0)
  await expect(page.getByText('تم تطبيق الاقتراح')).toBeVisible()
  expect(api.suggestionCalls).toEqual(['apply:too_old'])
})

test('suggestion banner: dismiss', async ({ page }) => {
  const api = await mockApi(page, { loggedIn: true })
  await page.goto('/')
  await page.getByRole('region', { name: 'اقتراح' }).getByRole('button', { name: 'لا شكراً' }).click()
  await expect(page.getByRole('region', { name: 'اقتراح' })).toHaveCount(0)
  expect(api.suggestionCalls).toEqual(['dismiss:too_old'])
})

test('settings history groups learner entries under their heading', async ({ page }) => {
  await mockApi(page, { loggedIn: true, learnerChange: true })
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: 'ما تعلّمه التطبيق' })).toBeVisible()
  await expect(page.getByText('زادت أهمية عرض الشارع')).toBeVisible()
})
