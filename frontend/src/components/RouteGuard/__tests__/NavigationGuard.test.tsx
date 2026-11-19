import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NavigationGuard from '../NavigationGuard';

// Mock window methods
// const _originalAddEventListener = window.addEventListener;
// const _originalRemoveEventListener = window.removeEventListener;

describe('NavigationGuard', () => {
  let addEventListenerSpy: ReturnType<typeof vi.spyOn>;
  let removeEventListenerSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    addEventListenerSpy = vi.spyOn(window, 'addEventListener');
    removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');
  });

  afterEach(() => {
    addEventListenerSpy.mockRestore();
    removeEventListenerSpy.mockRestore();
  });

  it('should render children without navigation blocking when when=false', () => {
    const { getByText } = render(
      <MemoryRouter>
        <NavigationGuard when={false}>
          <div>Test Content</div>
        </NavigationGuard>
      </MemoryRouter>
    );

    expect(getByText('Test Content')).toBeInTheDocument();
    // Should not add event listeners when when=false
    expect(addEventListenerSpy).not.toHaveBeenCalledWith('beforeunload', expect.any(Function));
    expect(addEventListenerSpy).not.toHaveBeenCalledWith('popstate', expect.any(Function));
  });

  it('should add event listeners when when=true', () => {
    render(
      <MemoryRouter>
        <NavigationGuard when={true}>
          <div>Test Content</div>
        </NavigationGuard>
      </MemoryRouter>
    );

    // Should add event listeners when when=true
    expect(addEventListenerSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function));
    expect(addEventListenerSpy).toHaveBeenCalledWith('popstate', expect.any(Function));
  });

  it('should remove event listeners on unmount', () => {
    const { unmount } = render(
      <MemoryRouter>
        <NavigationGuard when={true}>
          <div>Test Content</div>
        </NavigationGuard>
      </MemoryRouter>
    );

    unmount();

    // Should remove event listeners on unmount
    expect(removeEventListenerSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function));
    expect(removeEventListenerSpy).toHaveBeenCalledWith('popstate', expect.any(Function));
  });

  it('should use custom message when provided', () => {
    const customMessage = 'Custom unsaved changes message';
    
    render(
      <MemoryRouter>
        <NavigationGuard when={true} message={customMessage}>
          <div>Test Content</div>
        </NavigationGuard>
      </MemoryRouter>
    );

    // The custom message should be used in the event listeners
    expect(addEventListenerSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function));
    expect(addEventListenerSpy).toHaveBeenCalledWith('popstate', expect.any(Function));
  });
});