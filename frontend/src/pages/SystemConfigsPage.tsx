import { useEffect, useState } from 'react';
import { usePageTitle } from '../hooks/usePageTitle';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { PageBanner } from '../components/ui/PageBanner';
import { apiClient } from '../services/apiClient';
import { Link } from 'react-router-dom';

interface SystemStatus {
  status: string;
  uptime: number;
  version: string;
  python_version: string;
  platform: string;
  environment: string;
}

interface SystemInfo {
  application: { name: string; version: string; environment: string; debug: boolean };
  system: { hostname: string; platform: string; architecture: string; processor: string };
  python: { version: string; implementation: string; compiler: string };
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${d}d ${h}h ${m}m`;
}

function SystemConfigsPage() {
  usePageTitle('System Configs', 'The system status + the config surfaces — the _28 Phase-5 roundup');
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, i] = await Promise.all([
        apiClient.get<SystemStatus>('/api/v1/system/status'),
        apiClient.get<SystemInfo>('/api/v1/system/info'),
      ]);
      if (s.data) setStatus(s.data as SystemStatus);
      if (i.data) setInfo(i.data as SystemInfo);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const CONFIG_SURFACES = [
    { to: '/settings', label: 'Settings', hint: 'The application settings' },
    { to: '/providers/cloud', label: 'Cloud Providers', hint: 'The cloud roof (the A1 split); local daemons live under Local Providers' },
    { to: '/cognitive-pipeline', label: 'Pipeline Config', hint: 'The cognitive pipeline' },
    { to: '/speech', label: 'Speech', hint: 'The TTS/STT + the test facility' },
    { to: '/local-services', label: 'Local Services', hint: 'The local providers + the capabilities they power' },
    { to: '/notifications-config', label: 'Notifications', hint: 'The sounds + the mute' },
  ];

  return (
    <ErrorBoundary>
      <div className="p-6">
        <PageBanner
          title="System Configs"
          className="mb-6"
          tooltip="The system status + the config surfaces — the roundup page."
        />

        <div className="flex items-center justify-end mb-3">
          <button type="button" className="btn btn-sm btn-primary" onClick={() => void load()} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>

        {error && (
          <div className="alert alert-error text-sm mb-4">
            <span>{error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div className="card bg-base-100 shadow-md">
            <div className="card-body p-4">
              <h2 className="card-title text-sm">The system status</h2>
              {status ? (
                <dl className="text-sm space-y-1">
                  <div className="flex justify-between">
                    <dt className="opacity-60">Health</dt>
                    <dd className={status.status === 'healthy' ? 'text-success font-medium' : 'text-error font-medium'}>{status.status}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="opacity-60">Uptime</dt>
                    <dd className="font-mono">{formatUptime(status.uptime)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="opacity-60">Version</dt>
                    <dd className="font-mono">{status.version}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="opacity-60">Environment</dt>
                    <dd>{status.environment}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="opacity-60">Python</dt>
                    <dd className="font-mono">{status.python_version}</dd>
                  </div>
                </dl>
              ) : (
                <p className="text-xs opacity-60">{loading ? 'Loading…' : 'Unavailable'}</p>
              )}
            </div>
          </div>

          <div className="card bg-base-100 shadow-md">
            <div className="card-body p-4">
              <h2 className="card-title text-sm">The system info</h2>
              {info ? (
                <dl className="text-sm space-y-1">
                  <div className="flex justify-between">
                    <dt className="opacity-60">Application</dt>
                    <dd>{info.application.name} {info.application.version}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="opacity-60">Host</dt>
                    <dd className="font-mono">{info.system.hostname}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="opacity-60">Platform</dt>
                    <dd className="font-mono">{info.system.platform}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="opacity-60">Architecture</dt>
                    <dd className="font-mono">{info.system.architecture}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="opacity-60">Python impl</dt>
                    <dd className="font-mono">{info.python.implementation} {info.python.version}</dd>
                  </div>
                </dl>
              ) : (
                <p className="text-xs opacity-60">{loading ? 'Loading…' : 'Unavailable'}</p>
              )}
            </div>
          </div>
        </div>

        <div className="card bg-base-100 shadow-md">
          <div className="card-body p-4">
            <h2 className="card-title text-sm">The config surfaces</h2>
            <p className="text-xs opacity-70 mb-2">The Configuration section's pages — the roundup's pointers.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {CONFIG_SURFACES.map((c) => (
                <Link key={c.to} to={c.to} className="rounded-lg border border-base-300 p-3 hover:bg-base-200 transition-colors">
                  <div className="text-sm font-medium">{c.label}</div>
                  <div className="text-xs opacity-60">{c.hint}</div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
}

export default SystemConfigsPage;
