/**
 * Utility functions for formatting agent names and display text
 */

/**
 * Generate a short display name for an agent
 * Truncates long names and adds ellipsis if needed
 * @param name - The full agent name
 * @param maxLength - Maximum length for the display name (default: 20)
 * @returns Shortened display name
 */
export function getShortAgentName(name: string, maxLength: number = 20): string {
  if (name.length <= maxLength) {
    return name
  }
  return name.substring(0, maxLength - 1) + '…'
}

/**
 * Generate initials from an agent name
 * Useful for avatar badges
 * @param name - The agent name
 * @returns Two-letter initials
 */
export function getAgentInitials(name: string): string {
  const words = name.trim().split(/\s+/)
  if (words.length === 0) return '??'
  if (words.length === 1) {
    return words[0].substring(0, 2).toUpperCase()
  }
  return (words[0][0] + words[words.length - 1][0]).toUpperCase()
}

/**
 * Generate a color for an agent based on their name
 * Useful for consistent avatar colors
 * @param name - The agent name
 * @returns A color class name (from DaisyUI)
 */
export function getAgentColorClass(name: string): string {
  const colors = [
    'bg-primary',
    'bg-secondary',
    'bg-accent',
    'bg-info',
    'bg-success',
    'bg-warning',
    'bg-error'
  ]
  
  // Use hash of name to consistently pick a color
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = ((hash << 5) - hash) + name.charCodeAt(i)
    hash = hash & hash // Convert to 32bit integer
  }
  
  const index = Math.abs(hash) % colors.length
  return colors[index]
}

/**
 * Truncate session title for display
 * @param title - The session title
 * @param maxLength - Maximum length (default: 40)
 * @returns Truncated title with ellipsis if needed
 */
export function getTruncatedSessionTitle(title: string, maxLength: number = 40): string {
  if (title.length <= maxLength) {
    return title
  }
  return title.substring(0, maxLength - 1) + '…'
}

/**
 * Format agent name for display in different contexts
 * @param name - The agent name
 * @param context - Where the name will be displayed ('header', 'list', 'badge')
 * @returns Formatted name appropriate for the context
 */
export function formatAgentNameForContext(
  name: string,
  context: 'header' | 'list' | 'badge' = 'list'
): string {
  switch (context) {
    case 'header':
      // Header can be longer
      return getShortAgentName(name, 30)
    case 'badge':
      // Badge should be very short
      return getShortAgentName(name, 15)
    case 'list':
    default:
      // List items should be moderate length
      return getShortAgentName(name, 25)
  }
}

