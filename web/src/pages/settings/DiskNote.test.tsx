import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { DiskNote } from './StatusSection'

it('shows free space and warns when the disk is nearly full', () => {
  const { rerender } = render(<DiskNote disk={{ free_gb: 22.4, total_gb: 40 }} />)
  expect(screen.getByText(/مساحة القرص الحرة/).parentElement).toHaveTextContent('22.4')
  expect(screen.queryByRole('alert')).toBeNull()
  rerender(<DiskNote disk={{ free_gb: 3.1, total_gb: 40 }} />)
  expect(screen.getByRole('alert')).toHaveTextContent('المساحة شارفت على النفاد')
  rerender(<DiskNote disk={null} />)
  expect(screen.queryByText(/مساحة القرص/)).toBeNull()
})
