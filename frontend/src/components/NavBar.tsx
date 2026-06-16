import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

interface NavItem {
  to: string
  label: string
  badge?: 'warning'
}

const NAV_BY_ROLE: Record<string, NavItem[]> = {
  admin: [
    { to: '/sales',                  label: 'Dashboard' },
    { to: '/inventory/medicines',    label: 'Medicines' },
    { to: '/inventory/suppliers',    label: 'Suppliers' },
    { to: '/inventory/warehouses',   label: 'Warehouses' },
    { to: '/inventory/purchases',    label: 'Purchase Orders' },
    { to: '/inventory/stock',        label: 'Stock / Batches' },
    { to: '/inventory/expiry',       label: 'Expiry Alerts', badge: 'warning' },
    { to: '/sales/orders',           label: 'Sales Orders' },
    { to: '/sales/customers',        label: 'Customers' },
  ],
  inventory_manager: [
    { to: '/sales',                  label: 'Dashboard' },
    { to: '/inventory/medicines',    label: 'Medicines' },
    { to: '/inventory/suppliers',    label: 'Suppliers' },
    { to: '/inventory/warehouses',   label: 'Warehouses' },
    { to: '/inventory/purchases',    label: 'Purchase Orders' },
    { to: '/inventory/stock',        label: 'Stock / Batches' },
    { to: '/inventory/expiry',       label: 'Expiry Alerts', badge: 'warning' },
  ],
  sales_representative: [
    { to: '/sales',              label: 'Dashboard' },
    { to: '/sales/orders',       label: 'Orders' },
    { to: '/sales/customers',    label: 'Customers' },
    { to: '/customer/search',    label: 'New Order' },
  ],
  warehouse_staff: [
    { to: '/sales',              label: 'Dashboard' },
    { to: '/inventory/stock',    label: 'Stock / Batches' },
    { to: '/inventory/expiry',   label: 'Expiry Alerts', badge: 'warning' },
    { to: '/sales/orders',       label: 'Orders' },
  ],
  customer: [
    { to: '/customer', label: 'My Orders' },
  ],
}

const ROLE_LABELS: Record<string, string> = {
  admin:                'Admin',
  inventory_manager:    'Inventory Manager',
  sales_representative: 'Sales Rep',
  warehouse_staff:      'Warehouse Staff',
  customer:             'Customer',
}

export function NavBar() {
  const { role, logout } = useAuth()
  const navigate = useNavigate()
  const items = NAV_BY_ROLE[role ?? ''] ?? []

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="border-b border-slate-200 bg-white shadow-sm">
      <div className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
        <span className="shrink-0 text-base font-bold text-indigo-700">Pharma Dist.</span>

        <nav className="flex flex-1 items-center gap-1 overflow-x-auto">
          {items.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/sales' || item.to === '/customer'}
              className={({ isActive }) =>
                `shrink-0 flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`
              }
            >
              {item.label}
              {item.badge === 'warning' && (
                <span className="flex h-1.5 w-1.5 rounded-full bg-amber-500" />
              )}
            </NavLink>
          ))}
        </nav>

        <div className="flex shrink-0 items-center gap-3">
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
            {ROLE_LABELS[role ?? ''] ?? role}
          </span>
          <button
            onClick={handleLogout}
            className="text-sm text-slate-500 hover:text-red-600 transition-colors"
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  )
}
