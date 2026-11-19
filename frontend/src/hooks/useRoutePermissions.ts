import { useMemo } from 'react';
import { routes, getRouteByPath, hasRoutePermission } from '../config/routes';

interface UseRoutePermissionsProps {
  userPermissions?: string[];
  isAuthenticated?: boolean;
}

export const useRoutePermissions = ({
  userPermissions = [],
  isAuthenticated = true
}: UseRoutePermissionsProps = {}) => {
  
  // Get all accessible routes based on permissions
  const accessibleRoutes = useMemo(() => {
    return routes.filter(route => {
      // Skip 404 route for navigation
      if (route.path === '*') return false;
      
      // Check authentication requirement
      if (route.requiresAuth && !isAuthenticated) return false;
      
      // Check permissions
      return hasRoutePermission(route, userPermissions);
    });
  }, [userPermissions, isAuthenticated]);

  // Check if a specific route is accessible
  const canAccessRoute = (path: string): boolean => {
    const route = getRouteByPath(path);
    if (!route) return false;
    
    if (route.requiresAuth && !isAuthenticated) return false;
    
    return hasRoutePermission(route, userPermissions);
  };

  // Get navigation routes that are accessible
  const navigationRoutes = useMemo(() => {
    return accessibleRoutes;
  }, [accessibleRoutes]);

  return {
    accessibleRoutes,
    navigationRoutes,
    canAccessRoute,
    hasRoutePermission
  };
};

export default useRoutePermissions;