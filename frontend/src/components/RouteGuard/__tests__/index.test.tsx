import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import RouteGuard from '../index';
import type { RouteConfig } from '@/config/routes';

// Mock component for testing
const TestComponent = () => <div>Test Component Content</div>;

// Mock route configurations
const mockRoute: RouteConfig = {
  path: '/test',
  component: TestComponent,
  title: 'Test Route',
  requiresAuth: true,
  permissions: ['admin']
};

const mockPublicRoute: RouteConfig = {
  path: '/public',
  component: TestComponent,
  title: 'Public Route',
  requiresAuth: false
};

const mockRouteWithoutPermissions: RouteConfig = {
  path: '/no-perms',
  component: TestComponent,
  title: 'No Permissions Route',
  requiresAuth: true
};

describe('RouteGuard', () => {
  it('should render children when authenticated and has permissions', () => {
    render(
      <MemoryRouter initialEntries={['/test']}>
        <Routes>
          <Route
            path="/test"
            element={
              <RouteGuard
                route={mockRoute}
                userPermissions={['admin', 'user']}
                isAuthenticated={true}
              >
                <TestComponent />
              </RouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Test Component Content')).toBeInTheDocument();
  });

  it('should redirect when not authenticated for protected route', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/test']}>
        <Routes>
          <Route
            path="/test"
            element={
              <RouteGuard
                route={mockRoute}
                userPermissions={['admin']}
                isAuthenticated={false}
              >
                <TestComponent />
              </RouteGuard>
            }
          />
          <Route path="/" element={<div>Home Page</div>} />
        </Routes>
      </MemoryRouter>
    );

    // Should redirect to home (Navigate component doesn't render content)
    expect(container).not.toHaveTextContent('Test Component Content');
  });

  it('should render children for public routes without authentication', () => {
    render(
      <MemoryRouter initialEntries={['/public']}>
        <Routes>
          <Route
            path="/public"
            element={
              <RouteGuard
                route={mockPublicRoute}
                userPermissions={[]}
                isAuthenticated={false}
              >
                <TestComponent />
              </RouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Test Component Content')).toBeInTheDocument();
  });

  it('should show access denied when missing required permissions', () => {
    render(
      <MemoryRouter initialEntries={['/test']}>
        <Routes>
          <Route
            path="/test"
            element={
              <RouteGuard
                route={mockRoute}
                userPermissions={['user']} // Missing 'admin' permission
                isAuthenticated={true}
              >
                <TestComponent />
              </RouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Access Denied')).toBeInTheDocument();
    expect(screen.getByText(/You don't have permission to access this page/)).toBeInTheDocument();
    expect(screen.getByText(/Required permissions: admin/)).toBeInTheDocument();
  });

  it('should render custom fallback when provided', () => {
    const CustomFallback = () => <div>Custom Access Denied</div>;

    render(
      <MemoryRouter initialEntries={['/test']}>
        <Routes>
          <Route
            path="/test"
            element={
              <RouteGuard
                route={mockRoute}
                userPermissions={['user']}
                isAuthenticated={true}
                fallback={<CustomFallback />}
              >
                <TestComponent />
              </RouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Custom Access Denied')).toBeInTheDocument();
    expect(screen.queryByText('Access Denied')).not.toBeInTheDocument();
  });

  it('should render children when route has no permission requirements', () => {
    render(
      <MemoryRouter initialEntries={['/no-perms']}>
        <Routes>
          <Route
            path="/no-perms"
            element={
              <RouteGuard
                route={mockRouteWithoutPermissions}
                userPermissions={[]}
                isAuthenticated={true}
              >
                <TestComponent />
              </RouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Test Component Content')).toBeInTheDocument();
  });

  it('should handle empty permissions array gracefully', () => {
    render(
      <MemoryRouter initialEntries={['/no-perms']}>
        <Routes>
          <Route
            path="/no-perms"
            element={
              <RouteGuard
                route={mockRouteWithoutPermissions}
                userPermissions={[]}
                isAuthenticated={true}
              >
                <TestComponent />
              </RouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Test Component Content')).toBeInTheDocument();
  });
});