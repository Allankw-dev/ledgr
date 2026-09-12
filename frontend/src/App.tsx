import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from './pages/LoginPage';
import { ForgotPasswordPage } from './pages/ForgotPasswordPage';
import { ResetPasswordPage } from './pages/ResetPasswordPage';
import { DashboardPage } from './pages/DashboardPage';
import { StudentsPage } from './pages/StudentsPage';
import { ClassesPage } from './pages/ClassesPage';
import { InvoicesPage } from './pages/InvoicesPage';
import { AssistantPage } from './pages/AssistantPage';
import { AnnouncementsPage } from './pages/AnnouncementsPage';
import { MessagesPage } from './pages/MessagesPage';
import { AuditLogPage } from './pages/AuditLogPage';
import { SecurityPage } from './pages/SecurityPage';
import { GuardianRequestsPage } from './pages/GuardianRequestsPage';
import { ParentDashboardPage } from './pages/ParentDashboardPage';
import { ParentInvoicesPage } from './pages/ParentInvoicesPage';
import { ParentReceiptsPage } from './pages/ParentReceiptsPage';
import { ParentAssistantPage } from './pages/ParentAssistantPage';
import { ParentProfilePage } from './pages/ParentProfilePage';
import { ParentSignUpPage } from './pages/ParentSignUpPage';
import { VerifyChildPage } from './pages/VerifyChildPage';
import { ClassGroupsPage } from './pages/ClassGroupsPage';
import { ParentClassGroupPage } from './pages/ParentClassGroupPage';
import { TeachersPage } from './pages/TeachersPage';
import { ProtectedRoute } from './components/ProtectedRoute';

const STAFF_ROLES = ['SUPER_ADMIN', 'SCHOOL_ADMIN', 'BURSAR'] as const;

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
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
          path="/classes"
          element={
            <ProtectedRoute allowedRoles={[...STAFF_ROLES]}>
              <ClassesPage />
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
          path="/messages"
          element={
            <ProtectedRoute allowedRoles={['SCHOOL_ADMIN', 'BURSAR']}>
              <MessagesPage />
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
          path="/audit-log"
          element={
            <ProtectedRoute allowedRoles={[...STAFF_ROLES]}>
              <AuditLogPage />
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
          path="/teachers"
          element={
            <ProtectedRoute allowedRoles={[...STAFF_ROLES]}>
              <TeachersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/class-groups"
          element={
            <ProtectedRoute allowedRoles={[...STAFF_ROLES, 'TEACHER']}>
              <ClassGroupsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/parent/class-group"
          element={
            <ProtectedRoute allowedRoles={['PARENT']}>
              <ParentClassGroupPage />
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
        <Route
          path="/parent/invoices"
          element={
            <ProtectedRoute allowedRoles={['PARENT']}>
              <ParentInvoicesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/parent/receipts"
          element={
            <ProtectedRoute allowedRoles={['PARENT']}>
              <ParentReceiptsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/parent/assistant"
          element={
            <ProtectedRoute allowedRoles={['PARENT']}>
              <ParentAssistantPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/parent/profile"
          element={
            <ProtectedRoute allowedRoles={['PARENT']}>
              <ParentProfilePage />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
