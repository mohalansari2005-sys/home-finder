import { test } from '@playwright/test'
import { mockApi } from './fixtures'

// Saves screenshots to test-results/screens/ (gitignored) for visual review.
const dir = 'test-results/screens'

for (const scheme of ['light', 'dark'] as const) {
  test(`m4 screens ${scheme}`, async ({ page }, info) => {
    const n = `${info.project.name}-${scheme}`
    await page.emulateMedia({ colorScheme: scheme })
    await mockApi(page, { loggedIn: true, learnerChange: true, cardCount: 3 })
    await page.goto('/')
    await page.getByRole('article').first().waitFor()
    await page.screenshot({ path: `${dir}/m4-${n}-feed-banner.png` })
    await page.getByRole('article').first().getByRole('button', { name: 'استبعاد' }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'بعيد' }).click()
    await page.waitForTimeout(500)
    await page.screenshot({ path: `${dir}/m4-${n}-reject-sheet.png` })
    await page.keyboard.press('Escape')
    await page.goto('/?compare=1,2')
    await page.getByRole('article').first().waitFor()
    await page.screenshot({ path: `${dir}/m4-${n}-compare-mode.png` })
    await page.goto('/compare?ids=1,2,3')
    await page.getByRole('table').waitFor()
    await page.screenshot({ path: `${dir}/m4-${n}-compare.png`, fullPage: true })
    await page.goto('/settings')
    await page.getByText('ما تعلّمه التطبيق').waitFor()
    await page.screenshot({ path: `${dir}/m4-${n}-history.png`, fullPage: true })
    if (info.project.name === 'desktop') {
      await page.goto('/')
      await page.getByRole('button', { name: 'اختصارات لوحة المفاتيح' }).click()
      await page.waitForTimeout(300)
      await page.screenshot({ path: `${dir}/m4-${n}-shortcuts.png` })
    }
  })
}
