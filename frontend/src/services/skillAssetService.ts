/**
 * Skills management service (2026-08-14).
 *
 * The image-management model applied to skills — read-only v1:
 * browse (loader-validated list + curated flag), search/filter,
 * and the in-use (skill → agents) view. Write ops (import/export/
 * delete) arrive organically — skills are DIRECTORIES with
 * SKILL.md inside, not single files like images.
 */

import { apiClient } from './apiClient';

export interface SkillAsset {
  name: string;
  description: string;
  category: string;
  tags: string[];
  version: string;
  author: string;
  related_skills: string[];
  curated: boolean;
  valid: boolean;
  errors: string[];
  warnings: string[];
  path: string;
  body: string;
}

export interface SkillListResponse {
  skills: SkillAsset[];
  total: number;
}

export interface SkillAssignment {
  skill: string;
  agents: string[];
  sources: { file: string[]; derived: string[] };
}

export interface SkillsInUseResponse {
  assignments: SkillAssignment[];
  total: number;
}

export const skillAssetService = {
  async listSkills(params: { curated?: 'all' | 'true' | 'false'; q?: string } = {}): Promise<SkillListResponse> {
    const qs = new URLSearchParams();
    if (params.curated && params.curated !== 'all') qs.set('curated', params.curated);
    if (params.q) qs.set('q', params.q);
    const q = qs.toString();
    const { data } = await apiClient.get<SkillListResponse>(`/api/v1/skills${q ? `?${q}` : ''}`);
    return data!;
  },

  async listInUse(): Promise<SkillsInUseResponse> {
    const { data } = await apiClient.get<SkillsInUseResponse>('/api/v1/skills/in-use');
    return data!;
  },
};
