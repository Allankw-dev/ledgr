import { type ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { IdleTimeoutGuard } from './IdleTimeoutGuard';
import type { UserRole } from '../types';

interface ProtectedRouteProps {
  children: ReactNode;
  allowedRoles?: UserRole[];
}

// Note: this only prevents a logged-in user from *navigating* to a screen
// meant for a different role — it's a UX guard, not the actual security
// boundary. The real enforcement lives server-side: every backend endpoint
// checks the role and, for parents, filters by the student_guardians link
// table regardless of what the frontend does or doesn't render.
export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { token, user } = useAuthStore();
  if (!token) return <Navigate to="/login" replace />;

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <Navigate to={user.role === 'PARENT' ? '/parent/dashboard' : '/dashboard'} replace />;
  }

  return <IdleTimeoutGuard>{children}</IdleTimeoutGuard>;
}
