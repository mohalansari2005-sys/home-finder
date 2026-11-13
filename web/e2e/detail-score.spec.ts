import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

const breakdown = {
  total: 71, missing: ['street_width'],
  contributions: [
    { factor: 'price', value: 1, weight: 1, delta: 8.1 }, { factor: 'commute_work', value: 0.9, weight: 1, delta: 6.5 },
    { factor: 'yard', value: 1, weight: 0.3, delta: 2.4 }, { factor: 'building_age', value: 0, weight: 0.6, delta: -4.9 },
  ],
}

test('detail explains the score', async ({ page }) => {
  await mockApi(page, { loggedIn: true, breakdown })
  await page.goto('/listing/1')
  await expect(page.getByRole('heading', { name: /لماذا/ })).toBeVisible()
  await expect(page.getByTestId('plus')).toHaveCount(3)
  await expect(page.getByTestId('minus')).toHaveText('حداثة البناء')
  await page.getByRole('button', { name: 'كل التفاصيل' }).click()
  await expect(page.getByText(/بيانات ناقصة/)).toContainText('عرض الشارع')
  await page.screenshot({ path: `test-results/screens/${test.info().project.name}-score.png`, fullPage: true })
})

test('detail without a score', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/listing/1')
  await expect(page.getByText('لا يوجد تقييم بعد')).toBeVisible()
})
