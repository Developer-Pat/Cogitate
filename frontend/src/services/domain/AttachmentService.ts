// File attachment upload service
/**
 * Attachment Service
 * 
 * Handles file uploads to chat sessions.
 */

import { apiClient } from '../apiClient'

export interface AttachmentMetadata {
  id: number
  session_id: number
  original_filename: string
  stored_filename: string
  file_type: string
  file_size: number
  file_path: string
  mime_type: string | null
  created_at: string
}

export interface AttachmentListResponse {
  attachments: AttachmentMetadata[]
  total: number
}

export class AttachmentService {
  private basePath = '/api/v1/chat'

  /**
   * Upload a file attachment to a chat session.
   */
  async uploadAttachment(sessionId: number, file: File): Promise<AttachmentMetadata> {
    const formData = new FormData()
    formData.append('file', file)

    const endpoint = `${this.basePath}/${sessionId}/attachments`
    
    const response = await apiClient.upload<AttachmentMetadata>(endpoint, formData)

    return response.data!
  }

  /**
   * Upload multiple file attachments to a chat session.
   */
  async uploadBatch(sessionId: number, files: File[]): Promise<AttachmentListResponse> {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })

    const endpoint = `${this.basePath}/${sessionId}/attachments/batch`
    
    const response = await apiClient.upload<AttachmentListResponse>(endpoint, formData)

    return response.data!
  }

  /**
   * List all attachments for a chat session.
   */
  async listAttachments(sessionId: number): Promise<AttachmentListResponse> {
    const endpoint = `${this.basePath}/${sessionId}/attachments`
    const response = await apiClient.get<AttachmentListResponse>(endpoint)
    return response.data!
  }

  /**
   * Delete an attachment.
   */
  async deleteAttachment(sessionId: number, attachmentId: number): Promise<void> {
    const endpoint = `${this.basePath}/${sessionId}/attachments/${attachmentId}`
    await apiClient.delete<void>(endpoint)
  }

  /**
   * Get download URL for an attachment.
   */
  getDownloadUrl(sessionId: number, attachmentId: number): string {
    return `${this.basePath}/${sessionId}/attachments/${attachmentId}/download`
  }

  /**
   * Validate file before upload.
   */
  validateFile(file: File): { valid: boolean; error?: string } {
    const maxSize = 10 * 1024 * 1024 // 10MB
    const allowedExtensions = [
      '.md', '.txt', '.py', '.json', '.csv', '.yaml', '.yml',
      '.pdf', '.docx', '.xlsx',
      '.png', '.jpg', '.jpeg', '.gif', '.svg'
    ]

    if (file.size > maxSize) {
      return {
        valid: false,
        error: `File too large (${(file.size / 1024 / 1024).toFixed(2)}MB). Max: 10MB`
      }
    }

    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!allowedExtensions.includes(ext)) {
      return {
        valid: false,
        error: `File type '${ext}' not allowed. Allowed: ${allowedExtensions.join(', ')}`
      }
    }

    return { valid: true }
  }

  /**
   * Format file size for display.
   */
  formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }
}

export const attachmentService = new AttachmentService()
