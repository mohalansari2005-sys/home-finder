import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { RejectReasonSheet } from './RejectReasonSheet'

it('submits chosen reason and note', async () => {
  const onSubmit = vi.fn()
  render(<RejectReasonSheet open listingTitle="فيلا" onSubmit={onSubmit} onCancel={() => {}} />)
  await userEvent.click(screen.getByRole('radio', { name: 'قديم' }))
  await userEvent.type(screen.getByLabelText('ملاحظة (اختياري)'), 'المطبخ صغير')
  await userEvent.click(screen.getByRole('button', { name: 'استبعاد' }))
  expect(onSubmit).toHaveBeenCalledWith({ reason_code: 'too_old', note: 'المطبخ صغير' })
})

it('skip submits without reason; escape cancels', async () => {
  const onSubmit = vi.fn(), onCancel = vi.fn()
  render(<RejectReasonSheet open listingTitle="فيلا" onSubmit={onSubmit} onCancel={onCancel} />)
  await userEvent.click(screen.getByRole('button', { name: 'تخطي' }))
  expect(onSubmit).toHaveBeenCalledWith({})
  await userEvent.keyboard('{Escape}')
  expect(onCancel).toHaveBeenCalled()
})

it('is a modal dialog; clicking the chosen reason again deselects it', async () => {
  const onSubmit = vi.fn()
  render(<RejectReasonSheet open listingTitle="فيلا" onSubmit={onSubmit} onCancel={() => {}} />)
  expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true')
  const chip = screen.getByRole('radio', { name: 'بعيد' })
  await userEvent.click(chip)
  expect(chip).toBeChecked()
  await userEvent.click(chip)
  await userEvent.click(screen.getByRole('button', { name: 'استبعاد' }))
  expect(onSubmit).toHaveBeenCalledWith({})
})
