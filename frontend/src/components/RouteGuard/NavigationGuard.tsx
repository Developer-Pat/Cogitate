import React, { useEffect } from 'react';

interface NavigationGuardProps {
  children: React.ReactNode;
  when?: boolean;
  message?: string;
}

const NavigationGuard: React.FC<NavigationGuardProps> = ({
  children,
  when = false,
  message = 'You have unsaved changes. Are you sure you want to leave?'
}) => {
  // Handle browser back/forward buttons and navigation blocking
  useEffect(() => {
    if (!when) return;

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = message;
      return message;
    };

    const handlePopState = (_event: PopStateEvent) => {
      if (when) {
        const confirmLeave = window.confirm(message);
        if (!confirmLeave) {
          // Prevent navigation by pushing the current state back
          window.history.pushState(null, '', window.location.href);
        }
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    window.addEventListener('popstate', handlePopState);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      window.removeEventListener('popstate', handlePopState);
    };
  }, [when, message]);

  return <>{children}</>;
};

export default NavigationGuard;