import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi, afterEach } from 'vitest'
import { Dashboard } from './Dashboard'
import { apiClient } from '../api/client'

afterEach(() => {
  vi.restoreAllMocks()
})

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('Dashboard', () => {
  it('renders the page title', () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: { success: true, data: { status: 'ok' } },
    })

    renderWithClient(<Dashboard />)

    expect(
      screen.getByRole('heading', { name: /pharma distribution & inventory management/i }),
    ).toBeInTheDocument()
  })

  it('shows the API status once the health check resolves', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: { success: true, data: { status: 'ok' } },
    })

    renderWithClient(<Dashboard />)

    expect(await screen.findByText('ok')).toBeInTheDocument()
  })
})
