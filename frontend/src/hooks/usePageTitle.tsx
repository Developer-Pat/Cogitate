import { useEffect } from 'react';
import { Helmet } from 'react-helmet-async';
import { formatPageTitle, getDynamicPageTitle } from '../config/pageTitles';

/**
 * Hook to set page title with automatic cleanup
 * @param title - The page title (without suffix)
 * @param description - Optional meta description
 */
export function usePageTitle(title: string, description?: string) {
  useEffect(() => {
    // Set title immediately for faster UX
    const previousTitle = document.title;
    document.title = formatPageTitle(title);

    return () => {
      document.title = previousTitle;
    };
  }, [title]);

  // Return Helmet component for SSR and meta tags
  return (
    <Helmet>
      <title>{formatPageTitle(title)}</title>
      {description && <meta name="description" content={description} />}
    </Helmet>
  );
}

/**
 * Hook for dynamic page titles (sessions, agents, etc.)
 * @param baseTitle - The dynamic title (e.g., session name)
 * @param parentTitle - The parent section (e.g., 'Sessions')
 * @param description - Optional meta description
 */
export function useDynamicPageTitle(baseTitle: string, parentTitle?: string, description?: string) {
  useEffect(() => {
    const previousTitle = document.title;
    document.title = getDynamicPageTitle(baseTitle, parentTitle);

    return () => {
      document.title = previousTitle;
    };
  }, [baseTitle, parentTitle]);

  return (
    <Helmet>
      <title>{getDynamicPageTitle(baseTitle, parentTitle)}</title>
      {description && <meta name="description" content={description} />}
    </Helmet>
  );
}
