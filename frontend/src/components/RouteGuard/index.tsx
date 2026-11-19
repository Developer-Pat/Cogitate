import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import type { RouteConfig } from '@/config/routes';

interface RouteGuardProps {
  children: React.ReactNode;
  route: RouteConfig;
  userPermissions?: string[];
  isAuthenticated?: boolean;
  fallback?: React.ReactNode;
}

const RouteGuard: React.FC<RouteGuardProps> = ({
  children,
  route,
  userPermissions = [],
  isAuthenticated = true, // Default to true for now since we don't have auth system
  fallback
}) => {
  const location = useLocation();

  // Check if route requires authentication
  if (route.requiresAuth && !isAuthenticated) {
    // Redirect to login with return url
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  // Check if user has required permissions
  if (route.permissions && route.permissions.length > 0) {
    const hasPermission = route.permissions.some(permission => 
      userPermissions.includes(permission)
    );
    
    if (!hasPermission) {
      return (
        fallback || (
          <div className="flex flex-col items-center justify-center min-h-64 p-8">
            <div className="text-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 text-warning mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <h2 className="text-2xl font-bold text-base-content mb-2">Access Denied</h2>
              <p className="text-readout mb-4">
                You don't have permission to access this page.
              </p>
              <p className="text-sm text-readout mb-6">
                Required permissions: {route.permissions.join(', ')}
              </p>
              <button
                onClick={() => window.history.back()}
                className="btn btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
              >
                Go Back
              </button>
            </div>
          </div>
        )
      );
    }
  }

  return <>{children}</>;
};

export default RouteGuard;