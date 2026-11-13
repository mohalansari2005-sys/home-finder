import { expect, test, type Page } from '@playwright/test'
import { mockApi } from './fixtures'

const qp = (page: Page, k: string) => new URL(page.url()).searchParams.get(k)
const art = (page: Page, n: number) => page.getByRole('article').filter({ hasText: `فيلا ${n}` })

test('compare two listings', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/?view=bookmarked')
  await page.getByRole('button', { name: 'وضع المقارنة' }).click()
  await art(page, 1).getByRole('button', { name: 'قارن' }).click()
  await expect(page.getByRole('button', { name: 'قارن (1)' })).toBeDisabled()
  await art(page, 2).getByRole('button', { name: 'قارن' }).click()
  await expect.poll(() => qp(page, 'compare')).toBe('1,2')
  await page.getByRole('button', { name: 'قارن (2)' }).click()
  await expect(page).toHaveURL(/\/compare\?ids=/)
  expect(qp(page, 'ids')).toBe('1,2')
  await expect(page.getByTestId('best-cell').first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'مقارنة عقارين' })).toBeVisible()
  // listing 1 has no age: shown as missing, listing 2 wins street width
  await expect(page.getByRole('row', { name: /عمر المبنى/ }).getByText('غير مذكور')).toBeVisible()
  await expect(page.getByRole('row', { name: /عرض الشارع/ }).getByTestId('best-cell')).toContainText('30')
})

test('compare page: remove a column, falling back to the feed under two', async ({ page }) => {
  await mockApi(page, { loggedIn: true, cardCount: 3 })
  await page.goto('/compare?ids=1,2,3')
  await expect(page.getByRole('columnheader')).toHaveCount(4)
  await page.getByRole('button', { name: /إزالة فيلا 3/ }).click()
  await expect.poll(() => qp(page, 'ids')).toBe('1,2')
  await page.getByRole('button', { name: /إزالة فيلا 2/ }).click()
  await expect.poll(() => qp(page, 'compare')).toBe('1')
  await expect(page.getByRole('button', { name: 'وضع المقارنة' })).toHaveAttribute('aria-pressed', 'true')
})

test('compare page without enough ids shows an empty state', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/compare?ids=1')
  await expect(page.getByText('اختاروا عقارين على الأقل')).toBeVisible()
})

test('phone: table scrolls inside its container, no page-level horizontal scroll', async ({ page }, info) => {
  test.skip(info.project.name !== 'phone')
  await mockApi(page, { loggedIn: true, cardCount: 3 })
  await page.goto('/compare?ids=1,2')
  const box = page.getByTestId('compare-scroll')
  await expect(box).toBeVisible()
  const m = await box.evaluate((el) => ({ sw: el.scrollWidth, cw: el.clientWidth }))
  expect(m.sw).toBeGreaterThan(m.cw)
  const page_ = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }))
  expect(page_.sw).toBeLessThanOrEqual(page_.cw)
  // label column pinned: still at the same viewport x after scrolling the container
  const label = page.getByRole('rowheader', { name: 'السعر', exact: true })
  const before = (await label.boundingBox())!.x
  await box.evaluate((el) => { el.scrollLeft = -120 })
  const after = (await label.boundingBox())!.x
  expect(Math.abs(after - before)).toBeLessThan(1)
  await expect(label).toHaveCSS('position', 'sticky')
  // and the feed in compare mode doesn't overflow either
  await page.goto('/?compare=1')
  await page.getByRole('article').first().waitFor()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})

test('phone: selection is capped at two with a toast', async ({ page }, info) => {
  test.skip(info.project.name !== 'phone')
  await mockApi(page, { loggedIn: true, cardCount: 3 })
  await page.goto('/?compare=1,2')
  await art(page, 3).getByRole('button', { name: 'قارن' }).click()
  await expect(page.getByText('الحد الأقصى للمقارنة 2')).toBeVisible()
  expect(qp(page, 'compare')).toBe('1,2')
})

test('shortcuts ignore typing', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop')
  await mockApi(page, { loggedIn: true })
  await page.goto('/')
  await art(page, 1).click()
  await page.getByRole('textbox').first().focus() // docked chat input
  await page.keyboard.press('b')
  await expect(art(page, 1).getByRole('button', { name: 'حفظ' })).toBeVisible()
  await page.locator('body').click({ position: { x: 5, y: 5 } })
  await page.keyboard.press('b')
  await expect(art(page, 1).getByRole('button', { name: 'محفوظ' })).toBeVisible()
  await page.keyboard.press('b')
  await expect(art(page, 1).getByRole('button', { name: 'حفظ' })).toBeVisible()
})

test('shortcuts: arrows move the selection, x opens the reason sheet, ? lists them', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop')
  await mockApi(page, { loggedIn: true, noSuggestions: true })
  await page.goto('/')
  await art(page, 1).click()
  await expect(page).toHaveURL(/id=1/)
  await page.locator('body').click({ position: { x: 5, y: 5 } })
  await page.keyboard.press('ArrowLeft')
  await expect(page).toHaveURL(/id=2/)
  await page.keyboard.press('ArrowRight')
  await expect(page).toHaveURL(/id=1/)
  await page.keyboard.press('x')
  await expect(page.getByRole('dialog')).toContainText('لماذا استبعدتم')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.keyboard.press('?')
  await expect(page.getByRole('dialog')).toContainText('اختصارات لوحة المفاتيح')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: 'اختصارات لوحة المفاتيح' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
})

test('shortcuts are desktop only', async ({ page }, info) => {
  test.skip(info.project.name === 'desktop')
  const api = await mockApi(page, { loggedIn: true })
  await page.goto('/')
  await art(page, 1).waitFor()
  await expect(page.getByRole('button', { name: 'اختصارات لوحة المفاتيح' })).toHaveCount(0)
  await page.keyboard.press('b')
  expect(api.reacts).toHaveLength(0)
})
