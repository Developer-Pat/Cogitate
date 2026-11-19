import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useRoutePermissions } from '../useRoutePermissions';

describe('useRoutePermissions', () => {
  it('should return accessible routes based on permissions', () => {
    const { result } = renderHook(() => 
      useRoutePermissions({
        userPermissions: ['admin', 'user'],
        isAuthenticated: true
      })
    );

    expect(result.current.accessibleRoutes).toBeDefined();
    expect(result.current.accessibleRoutes.length).toBeGreaterThan(0);
    
    // Should include routes that don't require specific permissions
    const dashboardRoute = result.current.accessibleRoutes.find(r => r.path === '/');
    expect(dashboardRoute).toBeDefined();
    
    // Should include routes where user has required permissions
    const configRoute = result.current.accessibleRoutes.find(r => r.path === '/cognitive-pipeline');
    expect(configRoute).toBeDefined();
  });

  it('should filter out routes when user lacks permissions', () => {
    const { result } = renderHook(() => 
      useRoutePermissions({
        userPermissions: ['user'], // Missing 'admin' and 'config_manager'
        isAuthenticated: true
      })
    );

    const configRoute = result.current.accessibleRoutes.find(r => r.path === '/cognitive-pipeline');
    expect(configRoute).toBeUndefined();
  });

  it('should filter out protected routes when not authenticated', () => {
    const { result } = renderHook(() => 
      useRoutePermissions({
        userPermissions: ['admin'],
        isAuthenticated: false
      })
    );

    const protectedRoutes = result.current.accessibleRoutes.filter(r => r.requiresAuth);
    expect(protectedRoutes).toHaveLength(0);
    
    // Public routes should still be accessible
    const publicRoutes = result.current.accessibleRoutes.filter(r => !r.requiresAuth);
    expect(publicRoutes.length).toBeGreaterThan(0);
  });

  it('should check if specific route is accessible', () => {
    const { result } = renderHook(() => 
      useRoutePermissions({
        userPermissions: ['admin'],
        isAuthenticated: true
      })
    );

    expect(result.current.canAccessRoute('/')).toBe(true);
    expect(result.current.canAccessRoute('/cognitive-pipeline')).toBe(true);
    expect(result.current.canAccessRoute('/nonexistent')).toBe(false);
  });

  it('should return navigation routes excluding dev routes', () => {
    const { result } = renderHook(() => 
      useRoutePermissions({
        userPermissions: ['admin', 'developer'],
        isAuthenticated: true
      })
    );

    const navigationRoutes = result.current.navigationRoutes;
    expect(navigationRoutes).toBeDefined();
    
    // Should include main routes
    const mainRoutes = navigationRoutes.filter(r => 
      ['/', '/logs', '/cognitive-pipeline', '/system-info'].includes(r.path)
    );
    expect(mainRoutes.length).toBeGreaterThan(0);
  });

  it('should handle empty permissions array', () => {
    const { result } = renderHook(() => 
      useRoutePermissions({
        userPermissions: [],
        isAuthenticated: true
      })
    );

    // Routes without permission requirements should be accessible
    const dashboardRoute = result.current.accessibleRoutes.find(r => r.path === '/');
    expect(dashboardRoute).toBeDefined();
    
    // Routes with permission requirements should be filtered out
    const configRoute = result.current.accessibleRoutes.find(r => r.path === '/cognitive-pipeline');
    expect(configRoute).toBeUndefined();
  });

  it('should handle default parameters', () => {
    const { result } = renderHook(() => useRoutePermissions());

    expect(result.current.accessibleRoutes).toBeDefined();
    expect(result.current.navigationRoutes).toBeDefined();
    expect(result.current.canAccessRoute).toBeDefined();
    expect(result.current.hasRoutePermission).toBeDefined();
  });

  it('should provide correct navigation routes for different permission levels', () => {
    // Test with admin permissions
    const { result: adminResult } = renderHook(() => 
      useRoutePermissions({
        userPermissions: ['admin', 'config_manager'],
        isAuthenticated: true
      })
    );

    const adminNavRoutes = adminResult.current.navigationRoutes;
    expect(adminNavRoutes.find(r => r.path === '/cognitive-pipeline')).toBeDefined();

    // Test with user permissions only
    const { result: userResult } = renderHook(() => 
      useRoutePermissions({
        userPermissions: ['user'],
        isAuthenticated: true
      })
    );

    const userNavRoutes = userResult.current.navigationRoutes;
    expect(userNavRoutes.find(r => r.path === '/cognitive-pipeline')).toBeUndefined();
    expect(userNavRoutes.find(r => r.path === '/')).toBeDefined();
  });
});