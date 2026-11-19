/**
 * SoundsService — the notification-sound assets (Assets → Sounds).
 *
 * Lists, uploads, deletes, restores the curated set
 * (GET/POST/DELETE /api/v1/sounds) — the wav-assets catalog
 * (the images-store pattern).
 */

import { apiClient, API_BASE_URL } from '../apiClient';

/**
 * THE ONE-BASE SOUND RESOLVER (2026-08-30, the user's no-sound
 * report): the playable bytes ride the API — the OLD /sounds static
 * mount was ripped out (the SPA-route collision) and the container
 * still played the dead path (the HTML fallback -> silent failures).
 * Every play site builds the URL HERE.
 */
export const soundFileUrl = (filename: string): string =>
  `${API_BASE_URL}/api/v1/sounds/${encodeURIComponent(filename)}/file`;

export interface SoundAsset {
  filename: string;
  url: string;
  size: number;
  mime: string;
  created_at: number;
  is_curated?: boolean;
  is_configured?: boolean;
}

export interface SoundListResponse {
  sounds: SoundAsset[];
  total: number;
  page: number;
  page_size: number;
}

export interface SoundUploadResult {
  filename: string;
  url: string;
  size: number;
}

export class SoundsService {
  private basePath = '/api/v1/sounds';

  async listSounds(
    page = 1,
    pageSize = 50,
    curated: 'all' | 'true' | 'false' = 'all',
    sortBy: 'filename' | 'size' | 'created_at' = 'filename',
    sortDir: 'asc' | 'desc' = 'asc',
  ): Promise<SoundListResponse> {
    const resp = await apiClient.get<SoundListResponse>(
      `${this.basePath}?page=${page}&page_size=${pageSize}&curated=${curated}&sort_by=${sortBy}&sort_dir=${sortDir}`
    );
    return resp.data as SoundListResponse;
  }

  async uploadSound(file: File): Promise<SoundUploadResult> {
    const form = new FormData();
    form.append('file', file);
    const resp = await apiClient.post<SoundUploadResult>(`${this.basePath}/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return resp.data as SoundUploadResult;
  }

  async deleteSound(filename: string): Promise<void> {
    await apiClient.delete(`${this.basePath}/${encodeURIComponent(filename)}`);
  }

  async restoreCurated(): Promise<{ restored: string[]; skipped: number; total: number }> {
    const resp = await apiClient.post(`${this.basePath}/restore-curated`);
    return resp.data as { restored: string[]; skipped: number; total: number };
  }
}

export const soundsService = new SoundsService();
