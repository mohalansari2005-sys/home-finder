import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { AppShell } from './AppShell'

const setWidth = (w: number) => Object.defineProperty(window, 'innerWidth', { value: w, configurable: true })

describe('AppShell', () => {
  it('phone shows bottom tabs', () => {
    setWidth(390)
    render(<MemoryRouter><AppShell><p>x</p></AppShell></MemoryRouter>)
    expect(screen.getByTestId('bottom-tabs')).toBeInTheDocument()
    expect(screen.queryByTestId('side-nav')).toBeNull()
  })
  it('tablet shows collapsible side nav with toggle', () => {
    setWidth(820)
    render(<MemoryRouter><AppShell><p>x</p></AppShell></MemoryRouter>)
    expect(screen.getByTestId('side-nav')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'القائمة' })).toBeInTheDocument()
  })
  it('desktop shows fixed side nav without toggle', () => {
    setWidth(1440)
    render(<MemoryRouter><AppShell><p>x</p></AppShell></MemoryRouter>)
    expect(screen.getByTestId('side-nav')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'القائمة' })).toBeNull()
  })
})
