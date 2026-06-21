import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import DashboardPage from './pages/dashboard';
import IncidentsPage from './pages/incidents';
import CamerasPage from './pages/cameras';
import AuditPage from './pages/audit';
import SettingsPage from './pages/settings';

function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center h-full p-6">
      <h2 className="text-4xl font-bold text-text-primary mb-2">404</h2>
      <p className="text-text-secondary mb-6">
        The page you're looking for doesn't exist.
      </p>
      <Link
        to="/dashboard"
        className="px-4 py-2 rounded-lg bg-primary text-white font-semibold hover:bg-primary-light transition-colors"
      >
        Go to Dashboard
      </Link>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-bg-page">
        <Sidebar />
        <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
          <Header />
          <main className="flex-1 overflow-y-auto p-6">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/incidents" element={<IncidentsPage />} />
              <Route path="/cameras" element={<CamerasPage />} />
              <Route path="/audit" element={<AuditPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
