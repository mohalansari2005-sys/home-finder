import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

test('redirects to login, logs in, shows RTL feed', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')
  await expect(page).toHaveURL(/\/login/)
  await page.getByLabel('كلمة مرور العائلة').fill('wrong')
  await page.getByRole('button', { name: 'دخول' }).click()
  await expect(page.getByRole('alert')).toHaveText('كلمة المرور غير صحيحة')
  await page.getByLabel('كلمة مرور العائلة').fill('secret')
  await page.getByRole('button', { name: 'دخول' }).click()
  await expect(page.getByText('1,500,001 ر.س')).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
})

test('bookmark and reject from feed', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/')
  const first = page.getByRole('article').filter({ hasText: 'فيلا 1' })
  await first.getByRole('button', { name: 'حفظ' }).click()
  await expect(first.getByRole('button', { name: 'محفوظ' })).toBeVisible()
  const second = page.getByRole('article').filter({ hasText: 'فيلا 2' })
  await second.getByRole('button', { name: 'استبعاد' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'تخطي' }).click()
  await expect(page.getByRole('article').filter({ hasText: 'فيلا 2' })).toHaveCount(0)
})

test('navigation and detail adapt to viewport', async ({ page }, info) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/')
  await page.getByRole('article').filter({ hasText: 'فيلا 1' }).click()
  if (info.project.name === 'phone') {
    await expect(page.getByTestId('bottom-tabs')).toBeVisible()
    await expect(page).toHaveURL(/\/listing\/1$/)
  } else {
    await expect(page.getByTestId('side-nav')).toBeVisible()
    await expect(page).toHaveURL(/\?id=1|&id=1/)
    await expect(page.getByRole('button', { name: 'إغلاق' })).toBeVisible()
  }
  await expect(page.getByText('واتساب')).toBeVisible()
  await expect(page.getByText('غير مذكور').first()).toBeVisible()
})
