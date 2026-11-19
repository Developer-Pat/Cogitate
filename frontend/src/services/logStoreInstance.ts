import type { LogEntry, LogFilter } from '../types'

// Note: Cannot import frontendLoggingService here due to circular dependency
// frontendLoggingService depends on logStoreInstance, so this is a bootstrap module

const STORAGE_KEY = 'cogitate_logs'
const MAX_STORED_LOGS = 500 // Keep last 500 logs in localStorage

/**
 * Global singleton LogStore instance
 * This ensures all parts of the application use the same log store
 * Now with localStorage persistence across page navigation
 */
class LogStore {
  private logs: LogEntry[] = [];
  private maxLogs = 1000; // Keep last 1000 logs in memory
  private logCounter = 0; // Counter for unique IDs
  public readonly storeId: string; // Unique ID for this store instance

  constructor() {
    this.storeId = `store-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

    // Load logs from localStorage on initialization
    this.loadFromStorage()
  }

  private loadFromStorage() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        this.logs = parsed.logs || []
        this.logCounter = parsed.counter || 0
      }
    } catch {
      // Silently ignore - will use empty log array
    }
  }

  getLength(): number {
    return this.logs.length;
  }

  private saveToStorage() {
    try {
      const data = {
        logs: this.logs.slice(0, MAX_STORED_LOGS), // Only store last 500
        counter: this.logCounter,
        timestamp: Date.now()
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch {
      // localStorage might be full or disabled - silently ignore
    }
  }

  addLog(log: LogEntry) {
    // Ensure unique ID by adding counter
    const uniqueLog = {
      ...log,
      id: `log-${Date.now()}-${this.logCounter++}-${Math.random().toString(36).substr(2, 9)}`
    }
    this.logs.unshift(uniqueLog); // Add to beginning (most recent first)
    // Keep only the last maxLogs entries
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(0, this.maxLogs);
    }

    // Persist to localStorage
    this.saveToStorage()
  }

  getLogs(filters?: LogFilter): LogEntry[] {
    let filtered = [...this.logs];

    if (filters?.level?.length) {
      filtered = filtered.filter(log => filters.level!.includes(log.level));
    }

    if (filters?.source?.length) {
      filtered = filtered.filter(log => filters.source!.includes(log.source));
    }

    if (filters?.search) {
      const searchLower = filters.search.toLowerCase();
      filtered = filtered.filter(log =>
        log.message.toLowerCase().includes(searchLower) ||
        log.source.toLowerCase().includes(searchLower)
      );
    }

    if (filters?.startDate) {
      const startTime = new Date(filters.startDate).getTime();
      filtered = filtered.filter(log => new Date(log.timestamp).getTime() >= startTime);
    }

    if (filters?.endDate) {
      const endTime = new Date(filters.endDate).getTime();
      filtered = filtered.filter(log => new Date(log.timestamp).getTime() <= endTime);
    }

    return filtered;
  }

  getLogById(id: string): LogEntry | undefined {
    return this.logs.find(log => log.id === id);
  }

  getSources(): string[] {
    const sources = new Set(this.logs.map(log => log.source));
    return Array.from(sources).sort();
  }

  getStats() {
    const byLevel: Record<string, number> = {};
    const bySource: Record<string, number> = {};

    this.logs.forEach(log => {
      byLevel[log.level] = (byLevel[log.level] || 0) + 1;
      bySource[log.source] = (bySource[log.source] || 0) + 1;
    });

    // Count frontend vs backend logs
    const frontendLogs = this.logs.filter(log => 
      log.source === 'frontend' || log.source.startsWith('ui/') || log.source.startsWith('components/')
    ).length;
    const backendLogs = this.logs.filter(log => 
      log.source === 'backend' || log.source.startsWith('api/') || log.source.startsWith('services/')
    ).length;

    return {
      total: this.logs.length,
      byLevel,
      bySource,
      recentActivity: this.logs.filter(
        log => new Date(log.timestamp).getTime() > Date.now() - 60000
      ).length,
      frontendLogs,
      backendLogs
    };
  }

  clearLogs() {
    this.logs = [];
    this.logCounter = 0;
    localStorage.removeItem(STORAGE_KEY)
  }
}

// Create a single global instance using window object to ensure it's truly global
// This prevents module bundlers from creating multiple instances
declare global {
  interface Window {
    __cogitateLogStore?: LogStore;
  }
}

function getGlobalLogStore(): LogStore {
  if (!window.__cogitateLogStore) {
    window.__cogitateLogStore = new LogStore();
  }
  return window.__cogitateLogStore;
}

const globalLogStore = getGlobalLogStore();

export { globalLogStore };

