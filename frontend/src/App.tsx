import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { StudentsPage } from './pages/StudentsPage';
import { InvoicesPage } from './pages/InvoicesPage';
import { AssistantPage } from './pages/AssistantPage';
import { AnnouncementsPage } from './pages/AnnouncementsPage';
import { SecurityPage } from './pages/SecurityPage';
import { GuardianRequestsPage } from './pages/GuardianRequestsPage';
import { ParentDashboardPage } from './pages/ParentDashboardPage';
import { ParentSignUpPage } from './pages/ParentSignUpPage';
import { VerifyChildPage } from './pages/VerifyChildPage';
import { ProtectedRoute } from './components/ProtectedRoute';

const STAFF_ROLES = ['SUPER_ADMIN', 'SCHOOL_ADMIN', 'BURSAR'] as const;

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<ParentSignUpPage />} />
        <Route
          path="/verify-child"
          element={
            <ProtectedRoute allowedRoles={['PARENT']}>
              <VerifyChildPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute allowedRoles={[...STAFF_ROLES]}>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/students"
          element={
            <ProtectedRoute allowedRoles={[...STAFF_ROLES]}>
              <StudentsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/invoices"
          element={
            <ProtectedRoute allowedRoles={[...STAFF_ROLES]}>
              <InvoicesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/assistant"
          element={
            <ProtectedRoute allowedRoles={[...STAFF_ROLES]}>
              <AssistantPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/announcements"
          element={
            <ProtectedRoute allowedRoles={[...STAFF_ROLES]}>
              <AnnouncementsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/guardian-requests"
          element={
            <ProtectedRoute allowedRoles={[...STAFF_ROLES]}>
              <GuardianRequestsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/security"
          element={
            <ProtectedRoute allowedRoles={[...STAFF_ROLES]}>
              <SecurityPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/parent/dashboard"
          element={
            <ProtectedRoute allowedRoles={['PARENT']}>
              <ParentDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
