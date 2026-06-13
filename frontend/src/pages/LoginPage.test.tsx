import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { LoginPage } from './LoginPage'
import { AuthContext } from '../contexts/AuthContext'

// Minimal AuthContext value for tests
function makeAuthValue(overrides: Partial<{ login: () => Promise<void>; isAuthenticated: boolean }> = {}) {
  return {
    token: null,
    role: null,
    userId: null,
    isAuthenticated: false,
    login: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

function renderLoginPage(authValue = makeAuthValue()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/login']}>
        <AuthContext.Provider value={authValue}>
          <LoginPage />
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('LoginPage', () => {
  it('renders email and password fields', () => {
    renderLoginPage()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('shows validation error for invalid email', async () => {
    renderLoginPage()
    await userEvent.type(screen.getByLabelText(/email/i), 'not-an-email')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument()
  })

  it('shows validation error for empty password', async () => {
    renderLoginPage()
    await userEvent.type(screen.getByLabelText(/email/i), 'user@example.com')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText(/password is required/i)).toBeInTheDocument()
  })

  it('calls login with correct credentials', async () => {
    const login = vi.fn().mockResolvedValue(undefined)
    renderLoginPage(makeAuthValue({ login }))

    await userEvent.type(screen.getByLabelText(/email/i), 'sales@pharma.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'password123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith('sales@pharma.com', 'password123')
    })
  })

  it('shows api error when login fails', async () => {
    const login = vi.fn().mockRejectedValue(new Error('401'))
    renderLoginPage(makeAuthValue({ login }))

    await userEvent.type(screen.getByLabelText(/email/i), 'bad@pharma.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'wrongpass')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument()
  })
})
