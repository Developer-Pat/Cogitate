import { routes } from '../config/routes';

// THE TAB-TITLE FORMAT (2026-08-30, the user's consistency ask):
// every tab reads 'Page | Cogitate™' — the TM rides the suffix so
// the whole app inherits it from this one constant.
export const TITLE_SUFFIX = ' | Cogitate™';

/**
 * Get the full title for a route path
 * @param path - The route path (e.g., '/logs')
 * @returns The full page title (e.g., 'Logs | Cogitate')
 */
export function getPageTitle(path: string): string {
  const route = routes.find(r => r.path === path || r.path.includes(':'));
  
  if (route && route.title) {
    return `${route.title}${TITLE_SUFFIX}`;
  }
  
  // Default title if no route matches
  return `Cogitate${TITLE_SUFFIX}`;
}

/**
 * Get title for a specific route config
 * @param routeTitle - The route title from config
 * @returns The full page title with suffix
 */
export function formatPageTitle(routeTitle: string): string {
  return `${routeTitle}${TITLE_SUFFIX}`;
}

/**
 * Get title for dynamic pages (sessions, agents, etc.)
 * @param baseTitle - The base title (e.g., session name)
 * @param parentTitle - The parent section title (e.g., 'Sessions')
 * @returns The full page title (e.g., 'Session Name | Sessions | Cogitate')
 */
export function getDynamicPageTitle(baseTitle: string, parentTitle?: string): string {
  if (parentTitle) {
    return `${baseTitle} | ${parentTitle}${TITLE_SUFFIX}`;
  }
  return `${baseTitle}${TITLE_SUFFIX}`;
}
