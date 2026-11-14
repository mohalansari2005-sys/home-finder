import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

const HOME = [{ kind: 'home', name: 'المنزل', lat: 24.7, lng: 46.6 }]

test('plan a trip, mark visited, rate, notes and photo', async ({ page }, info) => {
  const api = await mockApi(page, { loggedIn: true, places: HOME })
  await page.goto('/')
  // the bottom tab bar (phone) or side nav carries the visits entry
  await page.getByRole('link', { name: 'الزيارات' }).first().click()
  await expect(page.getByRole('heading', { name: 'مقترحات حسب الحي' })).toBeVisible()
  await expect(page.getByText('النرجس، الياسمين')).toBeVisible()
  await expect(page.getByText('لا يمكن إضافتها لمسار لعدم توفر موقع')).toBeVisible()
  await expect(page.getByText('لا توجد رحلات بعد')).toBeVisible()

  await page.getByRole('button', { name: 'تخطيط زيارة', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('checkbox')).toHaveCount(2)
  await expect(dialog.getByRole('checkbox').first()).toBeChecked()
  await expect(dialog.getByLabel('وقت البدء')).toHaveValue('16:00')
  await expect(dialog.getByRole('radio', { name: 'المنزل الحالي' })).toBeChecked()
  await dialog.getByRole('radio', { name: '45' }).click()
  await dialog.getByRole('button', { name: 'إنشاء الرحلة' }).click()

  await expect(page).toHaveURL(/\/visits\/1$/)
  expect(api.tripPosts[0]).toMatchObject({ listing_ids: [1, 2], start_time: '16:00', origin_kind: 'home', minutes_per_visit: 45 })
  await expect(page.getByRole('heading', { name: 'رحلة السبت' })).toBeVisible()
  const stops = page.getByRole('list', { name: 'محطات الزيارة' }).getByRole('listitem')
  await expect(page.getByTestId('stop-time')).toHaveCount(2)
  await expect(page.getByTestId('stop-time').first()).toHaveText('4:10 – 4:40 م')
  await expect(page.locator('body')).not.toContainText('16:10')
  await expect(page.getByRole('link', { name: 'مراسلة المعلن عبر واتساب' })).toHaveAttribute('href', /wa\.me/)
  await expect(page.getByRole('link', { name: 'مراسلة المعلن عبر واتساب' })).toHaveCount(1) // only the stop with a phone
  // one directions link per stop, no multi-stop Google Maps trip
  await expect(page.getByRole('link', { name: 'افتح في خرائط Google' })).toHaveCount(0)
  await expect(stops.getByRole('link', { name: 'خرائط Google' })).toHaveCount(2)
  await expect(stops.first().getByRole('link', { name: 'خرائط Google' })).toHaveAttribute('href', /destination=24\.8,46\.60/)
  await expect(stops.first()).toBeVisible()

  const first = page.locator('#stop-10')
  await first.getByRole('radio', { name: 'تمت الزيارة' }).click()
  await expect(first.getByRole('radio', { name: 'تمت الزيارة' })).toBeChecked()
  await first.getByRole('button', { name: '5 من 5' }).click()
  await expect(first.getByRole('button', { name: '5 من 5' })).toHaveAttribute('aria-pressed', 'true')
  expect(api.stopPatches).toEqual([{ id: 10, contact_status: 'visited' }, { id: 10, rating: 5 }])

  await first.getByLabel('ملاحظات الزيارة').fill('الحوش واسع')
  await first.getByLabel('ملاحظات الزيارة').blur()
  await expect.poll(() => api.stopPatches.at(-1)).toEqual({ id: 10, notes: 'الحوش واسع' })

  await first.getByLabel('إضافة صورة').setInputFiles({ name: 'a.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('x') })
  await expect(first.getByRole('img', { name: 'صورة الزيارة 1' })).toBeVisible()
  await first.getByLabel('إضافة صورة').setInputFiles({ name: 'big.jpg', mimeType: 'image/jpeg', buffer: Buffer.alloc(8 * 1024 * 1024 + 1) })
  await expect(first.getByText('حجم الصورة يتجاوز 8 ميغابايت')).toBeVisible()
  expect(api.photoUploads).toBe(1)

  // route map with numbered stops on wide screens, none on phone / tablet portrait
  if (info.project.name === 'desktop') {
    const map = page.getByLabel('خريطة المسار')
    await expect(map.getByRole('button', { name: 'المحطة 2' })).toBeVisible()
    await map.getByRole('button', { name: 'المحطة 2' }).click()
    await expect(page.locator('#stop-11')).toBeInViewport()
  } else await expect(page.getByLabel('خريطة المسار')).toHaveCount(0)

  // the finished trip is listed back on the visits page
  await page.getByRole('link', { name: 'كل الرحلات' }).click()
  await expect(page.getByRole('link', { name: /محطتان/ })).toBeVisible()
})

test('price change and removed warnings, precheck and polling state', async ({ page }) => {
  const api = await mockApi(page, { loggedIn: true, places: HOME, trips: true, priceChange: true })
  await page.goto('/visits/1')
  const second = page.locator('#stop-11')
  await expect(second.getByText(/تغيّر السعر من/)).toContainText('2,050,000')
  await page.getByRole('button', { name: 'تحقق من الإعلانات' }).click()
  await expect(page.getByText('سيتم التحقق عند اتصال جهاز التحديث')).toBeVisible()
  expect(api.prechecks).toBe(1)
  await expect(page.getByText('جارٍ التحقق من الإعلانات')).toBeVisible()
})

test('contact status is a radio group that wraps without overflow or truncation', async ({ page }, info) => {
  await mockApi(page, { loggedIn: true, places: HOME, trips: true })
  await page.goto('/visits/1')
  const group = page.locator('#stop-10').getByRole('radiogroup', { name: 'حالة التواصل' })
  await expect(group.getByRole('radio')).toHaveCount(5)
  await group.getByRole('radio', { name: 'مؤكد' }).click()
  await expect(group.getByRole('radio', { name: 'مؤكد' })).toBeChecked()
  await expect(group.getByRole('radio', { name: 'لم نتواصل' })).not.toBeChecked()
  await expect(page.locator('#stop-10').getByRole('button', { name: '1 من 5' })).toHaveCount(0)
  const fit = await group.evaluate((g) => ({ box: g.scrollWidth <= g.clientWidth, items: [...g.querySelectorAll('[role=radio]')].every((i) => i.scrollWidth <= i.clientWidth) }))
  expect(fit).toEqual({ box: true, items: true })
  if (info.project.name === 'phone') await page.locator('#stop-10').screenshot({ path: 'test-results/screens/m5-phone-contact-status.png' })
  // stops without whatsapp offer the listing instead
  await expect(page.locator('#stop-11').getByRole('link', { name: 'فتح الإعلان' })).toBeVisible()
})

test('server 422 shows inline in the builder; missing home links to settings', async ({ page }) => {
  await mockApi(page, { loggedIn: true, places: HOME, tripError: 'حدد موقع المنزل في الإعدادات أولاً' })
  await page.goto('/visits')
  await page.getByRole('button', { name: 'تخطيط زيارة', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'إنشاء الرحلة' }).click()
  await expect(page.getByRole('alert')).toHaveText('حدد موقع المنزل في الإعدادات أولاً')
  await expect(page).toHaveURL(/\/visits$/)
})

test('builder without a home place offers the settings link', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/visits')
  await page.getByRole('button', { name: 'تخطيط زيارة', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('link', { name: 'تحديده من الإعدادات' })).toHaveAttribute('href', '/settings')
  await expect(dialog.getByRole('button', { name: 'إنشاء الرحلة' })).toBeDisabled()
})

test('empty states', async ({ page }) => {
  await mockApi(page, { loggedIn: true, noSaved: true })
  await page.goto('/visits')
  await expect(page.getByText('احفظ بعض العقارات أولاً لتخطيط زيارة')).toBeVisible()
  await expect(page.getByRole('link', { name: 'تصفح العقارات' })).toHaveAttribute('href', '/')
  await expect(page.getByText('لا توجد رحلات بعد')).toBeVisible()
})
