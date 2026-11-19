/**
 * ImageService — image asset management (Utilities → Images).
 *
 * Lists, uploads, deletes, imports/exports image assets
 * (GET/POST/DELETE /api/v1/images).
 */

import { apiClient } from '@/services/apiClient';

export interface ImageAsset {
  filename: string;
  url: string;
  size: number;
  mime: string;
  created_at: number;
  used_by: number[];
  is_curated?: boolean;
}

export interface ImageListResponse {
  images: ImageAsset[];
  total: number;
  page: number;
  page_size: number;
}

export interface ImageUploadResult {
  filename: string;
  url: string;
  size: number;
}

export interface ImageImportResult {
  added: string[];
  added_count: number;
  errors: string[];
}

export interface BulkUploadResult {
  added: { filename: string; url: string; size: number }[];
  errors: { filename: string; reason: string }[];
  total_requested: number;
  total_added: number;
  total_errors: number;
}

export interface BatchDeleteResult {
  deleted: string[];
  failed: { filename: string; reason: string }[];
  total_requested: number;
  total_deleted: number;
  total_failed: number;
}

export class ImageService {
  private basePath = '/api/v1/images';

  async listImages(
    page = 1,
    pageSize = 50,
    curated: 'all' | 'true' | 'false' = 'all',
    sortBy: 'filename' | 'size' | 'created_at' | 'mime' = 'filename',
    sortDir: 'asc' | 'desc' = 'asc',
  ): Promise<ImageListResponse> {
    const resp = await apiClient.get<ImageListResponse>(
      `${this.basePath}?page=${page}&page_size=${pageSize}&curated=${curated}&sort_by=${sortBy}&sort_dir=${sortDir}`
    );
    return resp.data as ImageListResponse;
  }

  async uploadImage(file: File, strip = false): Promise<ImageUploadResult> {
    const form = new FormData();
    form.append('file', file);
    const resp = await apiClient.post<ImageUploadResult>(`${this.basePath}/upload?strip=${strip}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return resp.data as ImageUploadResult;
  }

  async deleteImage(filename: string): Promise<void> {
    await apiClient.delete(`${this.basePath}/${encodeURIComponent(filename)}`);
  }

  async uploadImagesBulk(files: File[], strip = false): Promise<BulkUploadResult> {
    const form = new FormData();
    for (const f of files) form.append('files', f);
    const resp = await apiClient.post<BulkUploadResult>(`${this.basePath}/upload-bulk?strip=${strip}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return resp.data as BulkUploadResult;
  }

  async batchDelete(filenames: string[]): Promise<BatchDeleteResult> {
    const resp = await apiClient.post<BatchDeleteResult>(`${this.basePath}/batch-delete`, {
      filenames,
    });
    return resp.data as BatchDeleteResult;
  }

  async restoreCurated(): Promise<{ restored: string[]; skipped: number; total: number }> {
    const resp = await apiClient.post(`${this.basePath}/restore-curated`);
    return resp.data as { restored: string[]; skipped: number; total: number };
  }

  async importZip(file: File, strip = false): Promise<ImageImportResult> {
    const form = new FormData();
    form.append('file', file);
    const resp = await apiClient.post<ImageImportResult>(`${this.basePath}/import?strip=${strip}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return resp.data as ImageImportResult;
  }
}

export const imageService = new ImageService();
