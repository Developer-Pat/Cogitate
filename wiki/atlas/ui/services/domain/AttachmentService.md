---
title: AttachmentService
type: atlas-service
path: frontend/src/services/domain/AttachmentService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# AttachmentService

**Path**: `frontend/src/services/domain/AttachmentService.ts`
**Type**: service (class + singleton)

## Purpose
Chat attachment handling — upload (single/batch), list, delete, download URL, client-side validation + size formatting.

## Exported API
```typescript
export class AttachmentService {
  uploadAttachment(file, chatId?): Promise<Attachment>
  uploadBatch(files, chatId?): Promise<Attachment[]>
  listAttachments(chatId?): Promise<Attachment[]>
  deleteAttachment(attachmentId): Promise<void>
  getDownloadUrl(attachmentId): string
  validateFile(file): { valid: boolean; error?: string }
  formatFileSize(bytes): string
}
export const attachmentService = new AttachmentService()
```

## Endpoints
- `/api/v1/chat/attachments` (upload/list/delete)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |
| Attachment types | types | Data shapes |

## Usage Example
```tsx
const att = await attachmentService.uploadAttachment(file, sessionId)
```

## Data Flow / Notes
- validateFile/formatFileSize are client-side helpers; getDownloadUrl composes URL

## Related
- features/agentInteraction/ChatInterface.tsx — consumer
- hooks/useAgentInteraction.ts — consumer (attachmentIds in streaming)

## Deprecation / Obsolete Notes
Active service — 2 consumers. No deprecation markers.