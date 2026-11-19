import React, { useState, useEffect } from 'react';
import { sessionsService } from '@/services/domain/SessionsService';
import { AgentService } from '@/services/domain/AgentService';

interface SessionFiltersProps {
  onFilterChange: (filters: FilterState) => void;
}

interface FilterState {
  searchQuery: string;
  sortBy: 'date' | 'title' | 'count';
  sortOrder: 'asc' | 'desc';
  dateRange: 'all' | 'today' | 'week' | 'month';
  agents: AgentInfo[];
  agentFilter?: string | number;
  unnamedOnly: boolean;
}

interface SessionStats {
  total: number;
  today: number;
  week: number;
  month: number;
}

interface AgentInfo {
  id: string | number;
  name: string;
  profile_image_url?: string;
}

export const SessionFilters: React.FC<SessionFiltersProps> = ({ onFilterChange }) => {
  const [filters, setFilters] = useState<FilterState>({
    searchQuery: '',
    sortBy: 'date',
    sortOrder: 'desc',
    dateRange: 'all',
    agents: [],
    unnamedOnly: false
  });

  const [stats, setStats] = useState<SessionStats>({
    total: 0,
    today: 0,
    week: 0,
    month: 0
  });

  const [agents, setAgents] = useState<AgentInfo[]>([]);

  useEffect(() => {
    // Load agents for name mapping
    const loadAgents = async () => {
      try {
        const agentService = new AgentService();
        const agentList = await agentService.getAgents();
        setAgents(agentList.map(a => ({ id: a.id, name: a.name, profile_image_url: a.profileImageUrl })));
      } catch (error) {
        console.error('Failed to load agents:', error);
      }
    };
    loadAgents();
  }, []);

  useEffect(() => {
    const unsubscribe = sessionsService.subscribe((sessions) => {
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
      const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

      setStats({
        total: sessions.length,
        today: sessions.filter(s => new Date(s.createdAt) >= today).length,
        week: sessions.filter(s => new Date(s.createdAt) >= weekAgo).length,
        month: sessions.filter(s => new Date(s.createdAt) >= monthAgo).length
      });
    });

    return () => unsubscribe();
  }, []);

  useEffect(() => {
    onFilterChange({ ...filters, agents });
  }, [filters, onFilterChange, agents]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFilters(prev => ({ ...prev, searchQuery: e.target.value }));
  };

  const handleSortChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const [sortBy, sortOrder] = e.target.value.split('-') as ['date' | 'title' | 'count', 'asc' | 'desc'];
    setFilters(prev => ({ ...prev, sortBy, sortOrder }));
  };

  const handleDateRangeChange = (range: FilterState['dateRange']) => {
    setFilters(prev => ({ ...prev, dateRange: range }));
  };

  const handleAgentFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const agentId = e.target.value === 'all' ? undefined : e.target.value;
    setFilters(prev => ({ ...prev, agentFilter: agentId }));
  };

  const getDateRangeLabel = () => {
    switch (filters.dateRange) {
      case 'today': return 'Today';
      case 'week': return 'This Week';
      case 'month': return 'This Month';
      default: return 'All Time';
    }
  };

  return (
    <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
      <div className="card-body gap-[var(--card-gap)]">
        {/* Search and Filters Row */}
        <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
          {/* Search Input */}
          <div className="form-control w-full md:w-96">
            <div className="input-group">
              <input
                type="text"
                placeholder="Search sessions..."
                className="input input-bordered rounded-[var(--button-radius)] w-full"
                value={filters.searchQuery}
                onChange={handleSearchChange}
              />
              {filters.searchQuery && (
                <div className="tooltip tooltip-top" data-tip="Clear search">
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setFilters(prev => ({ ...prev, searchQuery: '' }))}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
                </div>
              )}
            </div>
          </div>

          {/* Unnamed Only Toggle */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              className="toggle toggle-sm"
              checked={filters.unnamedOnly}
              onChange={() => setFilters(prev => ({ ...prev, unnamedOnly: !prev.unnamedOnly }))}
            />
            <span className="text-sm">Unnamed only</span>
          </label>

          {/* Sort and Date Range */}
          <div className="flex flex-wrap gap-2">
            {/* Agent Filter */}
            {filters.agents.length > 0 && (
              <select
                className="select select-bordered rounded-[var(--button-radius)]"
                value={filters.agentFilter || 'all'}
                onChange={handleAgentFilterChange}
              >
                <option value="all">All Agents</option>
                {filters.agents.map(agent => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
            )}

            {/* Date Range Dropdown */}
            <div className="dropdown">
              <label tabIndex={0} className="btn btn-outline btn-sm">
                {getDateRangeLabel()}
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </label>
              <ul tabIndex={0} className="dropdown-content menu p-2 shadow bg-base-100 rounded-box z-50">
                <li><a onClick={() => handleDateRangeChange('all')}>All Time ({stats.total})</a></li>
                <li><a onClick={() => handleDateRangeChange('today')}>Today ({stats.today})</a></li>
                <li><a onClick={() => handleDateRangeChange('week')}>This Week ({stats.week})</a></li>
                <li><a onClick={() => handleDateRangeChange('month')}>This Month ({stats.month})</a></li>
              </ul>
            </div>

            {/* Sort Dropdown */}
            <select
              className="select select-bordered rounded-[var(--button-radius)]"
              value={`${filters.sortBy}-${filters.sortOrder}`}
              onChange={handleSortChange}
            >
              <option value="date-desc">Newest First</option>
              <option value="date-asc">Oldest First</option>
              <option value="title-asc">Title A-Z</option>
              <option value="title-desc">Title Z-A</option>
              <option value="count-desc">Most Messages</option>
              <option value="count-asc">Fewest Messages</option>
            </select>
          </div>
        </div>

        {/* Stats Row */}
        <div className="flex flex-wrap gap-4 text-sm">
          <div className="flex items-center gap-2">
            <span className="badge badge-primary badge-outline">Total: {stats.total}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="badge badge-secondary badge-outline">Today: {stats.today}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="badge badge-accent badge-outline">This Week: {stats.week}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="badge badge-muted badge-outline">This Month: {stats.month}</span>
          </div>
          {filters.searchQuery && (
            <div className="flex items-center gap-2">
              <span className="badge badge-info badge-outline">Searching: "{filters.searchQuery}"</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
