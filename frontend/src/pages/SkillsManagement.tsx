/**
 * Skills Management page (2026-08-14).
 *
 * The image-management model applied to the skill library —
 * browse (name/description/category/tags/validity), curated flag,
 * in-use view (which agents have which skill), and a body preview.
 * Read-only v1: upload/import/export/delete arrive organically
 * (skills are directories with SKILL.md inside, different zip
 * semantics than images).
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { usePageTitle } from '../hooks/usePageTitle';
import { PageBanner } from '../components/ui/PageBanner';
import { HelpButton } from '../components/help';
import { ScrollText } from 'lucide-react';
import { useNotificationStore } from '../stores/notificationStore';
import {
  skillAssetService,
  type SkillAsset,
  type SkillAssignment,
} from '../services/skillAssetService';

export default function SkillsManagement() {
  usePageTitle('Skills Management', 'Skill assets — browse, curated status, in-use view');

  const [skills, setSkills] = useState<SkillAsset[]>([]);
  const [total, setTotal] = useState(0);
  const [assignments, setAssignments] = useState<SkillAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [curatedFilter, setCuratedFilter] = useState<'all' | 'true' | 'false'>('all');
  const [expanded, setExpanded] = useState<string | null>(null);
  const { addError } = useNotificationStore();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [listResp, inUseResp] = await Promise.all([
        skillAssetService.listSkills(),
        skillAssetService.listInUse(),
      ]);
      setSkills(listResp.skills);
      setTotal(listResp.total);
      setAssignments(inUseResp.assignments);
    } catch (err) {
      addError('Skills', 'Failed to load skills');
      console.error('SkillsManagement load:', err);
    } finally {
      setLoading(false);
    }
  }, [addError]);

  useEffect(() => { load(); }, [load]);

  // used-by lookup: skill name -> agents (from the in-use view)
  const usedBy = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const a of assignments) {
      if (a.agents.length > 0) map.set(a.skill, a.agents);
    }
    return map;
  }, [assignments]);

  const filtered = useMemo(() => {
    let items = skills;
    if (curatedFilter === 'true') items = items.filter((s) => s.curated);
    if (curatedFilter === 'false') items = items.filter((s) => !s.curated);
    const q = search.trim().toLowerCase();
    if (q) {
      items = items.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q) ||
          s.tags.some((t) => t.toLowerCase().includes(q)) ||
          s.category.toLowerCase().includes(q)
      );
    }
    return items;
  }, [skills, curatedFilter, search]);

  // skill detail: the list endpoint carries the SKILL.md body for
  // EVERY skill (curated via the loader, agent-local read from the
  // file) — no second fetch, so agent-local skills preview too
  const openPreview = (skill: SkillAsset) => {
    if (expanded === skill.name) {
      setExpanded(null);
      return;
    }
    setExpanded(skill.name);
  };

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-7xl mx-auto">
        <PageBanner
          title="Skills Management"
          className="mb-8"
          tooltip="Skill assets — browse, curated status, in-use view. Skills ship with the app (curated) or live with an agent."
          action={
            <div className="flex items-center gap-2">
              <HelpButton context="skills" tooltipPosition="bottom" />
            </div>
          }
        />

        <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
          <div className="card-body gap-[var(--card-gap)]">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h2 className="card-title">Skills</h2>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Search name, description, tags…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="input input-bordered input-sm w-56"
                />
                <select
                  className="select select-bordered select-sm tooltip tooltip-top"
                  value={curatedFilter}
                  onChange={(e) => setCuratedFilter(e.target.value as 'all' | 'true' | 'false')}
                  data-tip="Filter by curated status"
                >
                  <option value="all">All</option>
                  <option value="true">Curated (ships with app)</option>
                  <option value="false">Agent-local</option>
                </select>
                <span className="text-sm text-readout">{total} total</span>
              </div>
            </div>

            {loading ? (
              <p className="text-sm text-readout">Loading skills…</p>
            ) : filtered.length === 0 ? (
              <div className="text-center py-8 opacity-70">
                <div className="text-4xl mb-2 text-readout">
                  <ScrollText className="h-10 w-10 mx-auto" />
                </div>
                <div>{total === 0 ? 'No skills found.' : 'No skills match the search.'}</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="table table-zebra w-full">
                  <thead>
                    <tr>
                      <th>Skill</th>
                      <th>Category</th>
                      <th>Tags</th>
                      <th>Status</th>
                      <th>Used By</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((skill) => (
                      <>
                        <tr key={skill.name} className={expanded === skill.name ? 'bg-base-300/40' : ''}>
                          <td className="min-w-56">
                            <div className="font-medium">{skill.name}</div>
                            <div className="text-xs text-readout line-clamp-2 max-w-md">{skill.description || '—'}</div>
                          </td>
                          <td className="text-sm">
                            {skill.curated ? (
                              <span className="tooltip tooltip-top" data-tip="Ships with the app (skills/ directory)">
                                <span className="badge badge-sm badge-primary badge-outline">curated</span>
                              </span>
                            ) : (
                              <span className="badge badge-sm badge-ghost">agent</span>
                            )}
                            <div className="text-xs text-readout mt-1">{skill.category}</div>
                          </td>
                          <td>
                            <div className="flex flex-wrap gap-1 max-w-56">
                              {skill.tags.slice(0, 4).map((t) => (
                                <span key={t} className="badge badge-sm badge-ghost">{t}</span>
                              ))}
                              {skill.tags.length > 4 && (
                                <span className="badge badge-sm badge-ghost">+{skill.tags.length - 4}</span>
                              )}
                            </div>
                          </td>
                          <td>
                            {skill.valid ? (
                              <span className="badge badge-sm badge-success badge-outline">valid</span>
                            ) : (
                              <span className="tooltip tooltip-top" data-tip={skill.errors.join('; ')}>
                                <span className="badge badge-sm badge-error badge-outline">invalid</span>
                              </span>
                            )}
                          </td>
                          <td>
                            {usedBy.has(skill.name) || usedBy.has(skill.name.replace(/\.skill$/, '')) ? (
                              <span className="badge badge-sm badge-success badge-outline">
                                agent {usedBy.get(skill.name)?.join(', ') || usedBy.get(skill.name.replace(/\.skill$/, ''))?.join(', ')}
                              </span>
                            ) : (
                              <span className="badge badge-sm badge-ghost">unused</span>
                            )}
                          </td>
                          <td>
                            <button
                              className="btn btn-xs btn-outline"
                              onClick={() => openPreview(skill)}
                            >
                              {expanded === skill.name ? 'Hide' : 'Preview'}
                            </button>
                          </td>
                        </tr>
                        {expanded === skill.name && (
                          <tr key={`${skill.name}-body`}>
                            <td colSpan={6} className="bg-base-100">
                              <div className="p-3 text-xs font-mono whitespace-pre-wrap max-h-64 overflow-y-auto bg-base-200/60 rounded-lg">
                                {skill.body
                                  ? skill.body.slice(0, 2000) + (skill.body.length > 2000 ? '\n… (truncated)' : '')
                                  : <span className="opacity-60">No preview available.</span>}
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
}
