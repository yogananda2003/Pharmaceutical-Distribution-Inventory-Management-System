import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthGuard } from './components/AuthGuard'
import { NavBar } from './components/NavBar'
import { AuthProvider } from './contexts/AuthContext'
import { LoginPage } from './pages/LoginPage'
import { MedicineList } from './pages/inventory/MedicineList'
import { PurchaseOrders } from './pages/inventory/PurchaseOrders'
import { StockBatches } from './pages/inventory/StockBatches'
import { SupplierList } from './pages/inventory/SupplierList'
import { WarehouseList } from './pages/inventory/WarehouseList'
import { OrderDetail } from './pages/customer/OrderDetail'
import { OrderHistory } from './pages/customer/OrderHistory'
import { PlaceOrder } from './pages/customer/PlaceOrder'
import { ProductSearch } from './pages/customer/ProductSearch'
import { CustomerList } from './pages/sales/CustomerList'
import { OrderManagement } from './pages/sales/OrderManagement'
import { SalesDashboard } from './pages/sales/SalesDashboard'

const STAFF_ROLES = ['admin', 'sales_representative', 'inventory_manager', 'warehouse_staff']
const INV_ROLES = ['admin', 'inventory_manager']

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/login" replace />} />

          {/* Customer portal */}
          <Route path="/customer" element={<AuthGuard roles="customer"><Layout><OrderHistory /></Layout></AuthGuard>} />
          <Route path="/customer/search" element={<AuthGuard roles={STAFF_ROLES}><Layout><ProductSearch /></Layout></AuthGuard>} />
          <Route path="/customer/order/new" element={<AuthGuard roles={STAFF_ROLES}><Layout><PlaceOrder /></Layout></AuthGuard>} />
          <Route path="/customer/orders" element={<AuthGuard roles={STAFF_ROLES}><Layout><OrderHistory /></Layout></AuthGuard>} />
          <Route path="/customer/orders/:id" element={<AuthGuard roles={STAFF_ROLES}><Layout><OrderDetail /></Layout></AuthGuard>} />

          {/* Sales portal */}
          <Route path="/sales" element={<AuthGuard roles={STAFF_ROLES}><Layout><SalesDashboard /></Layout></AuthGuard>} />
          <Route path="/sales/customers" element={<AuthGuard roles={STAFF_ROLES}><Layout><CustomerList /></Layout></AuthGuard>} />
          <Route path="/sales/orders" element={<AuthGuard roles={STAFF_ROLES}><Layout><OrderManagement /></Layout></AuthGuard>} />

          {/* Inventory / Stock management */}
          <Route path="/inventory/medicines" element={<AuthGuard roles={INV_ROLES}><Layout><MedicineList /></Layout></AuthGuard>} />
          <Route path="/inventory/suppliers" element={<AuthGuard roles={INV_ROLES}><Layout><SupplierList /></Layout></AuthGuard>} />
          <Route path="/inventory/warehouses" element={<AuthGuard roles={INV_ROLES}><Layout><WarehouseList /></Layout></AuthGuard>} />
          <Route path="/inventory/purchases" element={<AuthGuard roles={INV_ROLES}><Layout><PurchaseOrders /></Layout></AuthGuard>} />
          <Route path="/inventory/stock" element={<AuthGuard roles={STAFF_ROLES}><Layout><StockBatches /></Layout></AuthGuard>} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />
      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  )
}

export default App
