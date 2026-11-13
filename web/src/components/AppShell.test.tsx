import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'
import { AppShell } from './AppShell'
import { ChatProvider } from './chat/ChatProvider'

const setWidth = (w: number) => Object.defineProperty(window, 'innerWidth', { value: w, configurable: true })
const shell = (path = '/') => render(
  <QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={[path]}><ChatProvider><AppShell><p>x</p></AppShell></ChatProvider></MemoryRouter>
  </QueryClientProvider>,
) as unknown as ReactElement

beforeEach(() => localStorage.clear())

describe('AppShell', () => {
  it('phone shows bottom tabs including the assistant tab, and no floating chat', () => {
    setWidth(390)
    shell()
    expect(screen.getByTestId('bottom-tabs')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'المساعد' })).toHaveAttribute('href', '/assistant')
    expect(screen.getAllByRole('link')).toHaveLength(5)
    expect(screen.getByRole('link', { name: 'الزيارات' })).toHaveAttribute('href', '/visits')
    expect(screen.queryByTestId('side-nav')).toBeNull()
    expect(screen.queryByRole('button', { name: 'اسأل المساعد' })).toBeNull()
    expect(screen.queryByTestId('chat-dock')).toBeNull()
  })
  it('tablet shows collapsible side nav with toggle and a floating assistant button that opens a slide-over', async () => {
    setWidth(820)
    shell()
    expect(screen.getByTestId('side-nav')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'القائمة' })).toBeInTheDocument()
    expect(screen.queryByTestId('chat-dock')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'اسأل المساعد' }))
    const dialog = await screen.findByRole('dialog', { name: 'المساعد' })
    expect(dialog).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'رسالتك' })).toHaveFocus()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(screen.getByRole('button', { name: 'اسأل المساعد' })).toHaveFocus())
  })
  it('desktop shows fixed side nav without toggle and the chat docked, collapsible to a rail', async () => {
    setWidth(1440)
    shell()
    expect(screen.getByTestId('side-nav')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'القائمة' })).toBeNull()
    expect(screen.getByTestId('chat-dock')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'اسأل المساعد' })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'طي المساعد' }))
    expect(screen.queryByRole('textbox', { name: 'رسالتك' })).toBeNull()
    expect(localStorage.getItem('hf_chat_open')).toBe('0')
    expect(screen.getByRole('button', { name: 'فتح المساعد' })).toHaveFocus()
    await userEvent.click(screen.getByRole('button', { name: 'فتح المساعد' }))
    expect(screen.getByRole('textbox', { name: 'رسالتك' })).toHaveFocus()
  })
  it('narrow desktop (< 1440px) uses the floating button instead of the dock', () => {
    setWidth(1280)
    shell()
    expect(screen.queryByTestId('chat-dock')).toBeNull()
    expect(screen.getByRole('button', { name: 'اسأل المساعد' })).toBeInTheDocument()
  })
  it('hides the dock and the floating button on the assistant page itself', () => {
    setWidth(1440)
    shell('/assistant')
    expect(screen.queryByTestId('chat-dock')).toBeNull()
  })
})
