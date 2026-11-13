import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

test('edit filters and weights', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/settings')
  await page.getByLabel('أعلى سعر').fill('2000000')
  await page.getByLabel('حي', { exact: true }).fill('النرجس')
  await page.getByRole('button', { name: 'إضافة' }).click()
  await expect(page.getByRole('button', { name: 'إزالة النرجس' })).toBeVisible()
  await page.getByRole('button', { name: 'حفظ الفلاتر' }).click()
  await expect(page.getByText('تم الحفظ')).toBeVisible()
  // Radix sliders are keyboard driven: End jumps to the maximum
  await page.getByRole('slider', { name: 'عرض الشارع' }).focus()
  await page.keyboard.press('End')
  await page.getByRole('button', { name: 'حفظ الأهمية' }).click()
  await expect(page.getByLabel('عرض الشارع (مثبت)')).toBeVisible()
  await page.getByRole('button', { name: 'إلغاء تثبيت عرض الشارع' }).click()
  await expect(page.getByLabel('عرض الشارع (مثبت)')).toHaveCount(0)
})

test('invalid price shows the server error inline', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/settings')
  await page.getByLabel('أعلى سعر').fill('5')
  await page.getByRole('button', { name: 'حفظ الفلاتر' }).click()
  await expect(page.getByRole('alert')).toContainText('price_max')
})

test('set a place by pasting a google maps link', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/settings')
  const work = page.getByTestId('place-work')
  await work.getByLabel('الاسم').fill('المكتب')
  await work.getByPlaceholder('الصق إحداثيات أو رابط خرائط Google').fill('https://maps.google.com/?q=24.75,46.7')
  await page.getByRole('button', { name: 'حفظ الأماكن' }).click()
  await expect(page.getByText('سيُعاد حساب المسافات')).toBeVisible()
})

test('a bad coordinates paste is flagged and a paused adapter can be resumed', async ({ page }) => {
  await mockApi(page, { loggedIn: true, paused: true })
  await page.goto('/settings')
  await page.getByTestId('place-school').getByPlaceholder('الصق إحداثيات أو رابط خرائط Google').fill('hello')
  await expect(page.getByText('صيغة غير صحيحة')).toBeVisible()
  await page.getByRole('button', { name: 'استئناف' }).click()
  await expect(page.getByRole('button', { name: 'استئناف' })).toHaveCount(0)
})
