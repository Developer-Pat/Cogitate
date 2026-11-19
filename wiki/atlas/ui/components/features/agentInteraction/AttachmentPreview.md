---
title: AttachmentPreview
type: atlas-component
path: frontend/src/components/features/agentInteraction/AttachmentPreview.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# AttachmentPreview

**Path**: `frontend/src/components/features/agentInteraction/AttachmentPreview.tsx`
**Last Updated**: 2026-08-01

## Purpose
Chat-input attachment previews — file chips with extension-mapped icons (image/code/doc/default), name, formatted size, per-file remove (X), optional 'summarize' action (Sparkles), and upload progress bars.

## Props Interface
```typescript
interface AttachmentPreviewProps {
  files: FileList | File[]
  onRemove: (index: number) => void
  onSummarize?: (index: number) => void
  uploadProgress?: number[]
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| lucide-react icons | Library | X, File, FileText, Image, FileCode, Sparkles |

## Usage Example
```tsx
<AttachmentPreview files={files} onRemove={removeFile} onSummarize={summarize} uploadProgress={progress} />
```

## State Used
None — controlled via props.

## Related Components
- features/agentInteraction/ChatInterface.tsx — chat input attachments