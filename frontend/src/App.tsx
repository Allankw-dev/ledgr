import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';

// Every page loads lazily, split into its own chunk — without this the
// whole app (every admin page, every parent page, all ~25 routes) shipped
// as one ~920KB bundle that had to be downloaded and parsed before even
// the login screen could render. Now a first visit only pulls the chunk
// for the route actually being hit; everything else loads on demand as
// the person navigates there.
const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({ default: m.LoginPage })));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })));
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage').then((m) => ({ default: m.ResetPasswordPage })));
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })));
const StudentsPage = lazy(() => import('./pages/StudentsPage').then((m) => ({ default: m.StudentsPage })));
const ClassesPage = lazy(() => import('./pages/ClassesPage').then((m) => ({ default: m.ClassesPage })));
const InvoicesPage = lazy(() => import('./pages/InvoicesPage').then((m) => ({ default: m.InvoicesPage })));
const AssistantPage = lazy(() => import('./pages/AssistantPage').then((m) => ({ default: m.AssistantPage })));
const AnnouncementsPage = lazy(() => import('./pages/AnnouncementsPage').then((m) => ({ default: m.AnnouncementsPage })));
const MessagesPage = lazy(() => import('./pages/MessagesPage').then((m) => ({ default: m.MessagesPage })));
const AuditLogPage = lazy(() => import('./pages/AuditLogPage').then((m) => ({ default: m.AuditLogPage })));
const SecurityPage = lazy(() => import('./pages/SecurityPage').then((m) => ({ default: m.SecurityPage })));
const GuardianRequestsPage = lazy(() => import('./pages/GuardianRequestsPage').then((m) => ({ default: m.GuardianRequestsPage })));
const ParentDashboardPage = lazy(() => import('./pages/ParentDashboardPage').then((m) => ({ default: m.ParentDashboardPage })));
const ParentInvoicesPage = lazy(() => import('./pages/ParentInvoicesPage').then((m) => ({ default: m.ParentInvoicesPage })));
const ParentReceiptsPage = lazy(() => import('./pages/ParentReceiptsPage').then((m) => ({ default: m.ParentReceiptsPage })));
const ParentAssistantPage = lazy(() => import('./pages/ParentAssistantPage').then((m) => ({ default: m.ParentAssistantPage })));
const ParentProfilePage = lazy(() => import('./pages/ParentProfilePage').then((m) => ({ default: m.ParentProfilePage })));
const ParentSignUpPage = lazy(() => import('./pages/ParentSignUpPage').then((m) => ({ default: m.ParentSignUpPage })));
const VerifyChildPage = lazy(() => import('./pages/VerifyChildPage').then((m) => ({ default: m.VerifyChildPage })));
const ClassGroupsPage = lazy(() => import('./pages/ClassGroupsPage').then((m) => ({ default: m.ClassGroupsPage })));
const ParentClassGroupPage = lazy(() => import('./pages/ParentClassGroupPage').then((m) => ({ default: m.ParentClassGroupPage })));
const TeachersPage = lazy(() => import('./pages/TeachersPage').then((m) => ({ default: m.TeachersPage })));

const STAFF_ROLES = ['SUPER_ADMIN', 'SCHOOL_ADMIN', 'BURSAR'] as const;

function RouteLoadingFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-paper">
      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-700 to-cyan animate-pulse" />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteLoadingFallback />}>
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
      </Suspense>
    </BrowserRouter>
  );
}
