import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthGuard } from './components/AuthGuard'
import { AuthProvider } from './contexts/AuthContext'
import { LoginPage } from './pages/LoginPage'
import { OrderDetail } from './pages/customer/OrderDetail'
import { OrderHistory } from './pages/customer/OrderHistory'
import { PlaceOrder } from './pages/customer/PlaceOrder'
import { ProductSearch } from './pages/customer/ProductSearch'
import { CustomerList } from './pages/sales/CustomerList'
import { OrderManagement } from './pages/sales/OrderManagement'
import { SalesDashboard } from './pages/sales/SalesDashboard'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/login" replace />} />

          {/* Customer / Sales-rep portal — any authenticated user */}
          <Route
            path="/customer"
            element={
              <AuthGuard>
                <PortalLayout title="Customer Portal">
                  <OrderHistory />
                </PortalLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/customer/search"
            element={
              <AuthGuard>
                <PortalLayout title="Browse Products">
                  <ProductSearch />
                </PortalLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/customer/order/new"
            element={
              <AuthGuard>
                <PortalLayout title="Place Order">
                  <PlaceOrder />
                </PortalLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/customer/orders"
            element={
              <AuthGuard>
                <PortalLayout title="Order History">
                  <OrderHistory />
                </PortalLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/customer/orders/:id"
            element={
              <AuthGuard>
                <PortalLayout title="Order Details">
                  <OrderDetail />
                </PortalLayout>
              </AuthGuard>
            }
          />

          {/* Sales portal — sales_representative role */}
          <Route
            path="/sales"
            element={
              <AuthGuard role="sales_representative">
                <PortalLayout title="Sales Portal">
                  <SalesDashboard />
                </PortalLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/sales/customers"
            element={
              <AuthGuard role="sales_representative">
                <PortalLayout title="Customers">
                  <CustomerList />
                </PortalLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/sales/orders"
            element={
              <AuthGuard role="sales_representative">
                <PortalLayout title="Orders">
                  <OrderManagement />
                </PortalLayout>
              </AuthGuard>
            }
          />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

interface PortalLayoutProps {
  title: string
  children: React.ReactNode
}

function PortalLayout({ title, children }: PortalLayoutProps) {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-base font-semibold text-slate-800">Pharma Distribution — {title}</h1>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
    </div>
  )
}

export default App
