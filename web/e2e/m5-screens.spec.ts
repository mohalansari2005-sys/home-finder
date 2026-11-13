import { test } from '@playwright/test'
import { mockApi } from './fixtures'

// Saves screenshots to test-results/screens/ (gitignored) for visual review.
const dir = 'test-results/screens'
const HOME = [{ kind: 'home', name: 'المنزل', lat: 24.7, lng: 46.6 }]

for (const scheme of ['light', 'dark'] as const) {
  test(`m5 screens ${scheme}`, async ({ page }, info) => {
    const n = `${info.project.name}-${scheme}`
    await page.emulateMedia({ colorScheme: scheme })
    const api = await mockApi(page, { loggedIn: true, places: HOME, trips: true, priceChange: true })
    await page.goto('/visits')
    await page.getByRole('button', { name: 'تخطيط زيارة' }).waitFor()
    await page.screenshot({ path: `${dir}/m5-${n}-visits.png`, fullPage: true })
    await page.getByRole('button', { name: 'تخطيط زيارة' }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'إنشاء الرحلة' }).waitFor()
    await page.waitForTimeout(500)
    await page.screenshot({ path: `${dir}/m5-${n}-builder.png` })
    await page.keyboard.press('Escape')
    api.trips[0].stops[0].contact_status = 'visited'
    api.trips[0].stops[0].rating = 4
    api.trips[0].stops[0].notes = 'الحوش واسع والشارع هادئ'
    api.trips[0].warnings = ['skipped_no_location']
    api.trips[0].skipped_no_location = 1
    await page.goto('/visits/1')
    await page.getByRole('heading', { name: 'رحلة السبت' }).waitFor()
    await page.waitForTimeout(300)
    await page.screenshot({ path: `${dir}/m5-${n}-trip.png`, fullPage: true })
  })
}
