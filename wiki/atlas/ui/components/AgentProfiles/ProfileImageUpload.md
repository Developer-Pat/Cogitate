---
title: ProfileImageUpload
type: atlas-component
path: frontend/src/components/AgentProfiles/ProfileImageUpload.tsx
confidence: high
updated: 2026-09-10
tags: [type/component, domain/atlas-ui]
---

# ProfileImageUpload

**Path**: `frontend/src/components/AgentProfiles/ProfileImageUpload.tsx`
**Last Updated**: 2026-08-01

## Purpose
Profile image picker + uploader for agent profiles. Renders a preview thumbnail (the existing `currentImageUrl` or a locally selected file via `FileReader` data URL), a hidden native `<input type="file">` triggered by two DaisyUI buttons — **Upload** (native picker) and **Browse store** (opens `ProfileImagePicker`, the curated + uploads image store) — and an optional remove button. It validates file type (PNG/JPEG/WebP) and size (max 5 MB), shows a local preview immediately, and — when `profileId` is provided — uploads the file to the backend via `profileService.uploadProfileImage()` and reports the returned URL through `onImageUrlChange`. No cropping is performed.

## Props Interface
```typescript
interface ProfileImageUploadProps {
  profileId?: string
  currentImageUrl?: string
  onImageUrlChange: (imageUrl: string) => void
  onImageFileChange?: (file: File | null) => void
  isLoading?: boolean
  resetTrigger?: number  // Increment this to reset the component
}
```

| Prop | Type | Description |
|---|---|---|
| `profileId` | `string \| undefined` | Backend agent/profile ID. When present, selecting a file triggers an immediate upload; when absent, the file is only tracked locally for a deferred parent upload. |
| `currentImageUrl` | `string \| undefined` | Existing image URL shown as the preview (from parent form state / profile record). |
| `onImageUrlChange` | `(imageUrl: string) => void` | Called with the new image URL after a successful upload, or with `''` when the image is removed. |
| `onImageFileChange` | `(file: File \| null) => void \| undefined` | Called with the selected `File` (or `null` on removal) so the parent can hold the file for a later upload. |
| `isLoading` | `boolean` | Disables the file input, picker button, and remove button while a parent save is in flight. Defaults to `false`. |
| `resetTrigger` | `number` | Incrementing this value clears the local file selection and the native file input (used when the parent switches profiles or clears its `selectedImageFile`). Defaults to `0`. |

## Dependencies
| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`, `useRef`, `useEffect`) | hooks | Local state (`preview`, `uploading`, `error`, `localFile`), ref to the hidden file input, and mount / reset / preview-sync effects. |
| `profileService` (`../../services/domain/ProfileService`) | domain service | `uploadProfileImage(profileId, file)` performs the actual upload and returns the image URL (kept relative). |
| `ProfileImagePicker` (`./ProfileImagePicker`) | child component | Image-store browser opened by the **Browse store** button; `onSelect(url)` writes the picked URL into the form |
| `frontendLoggingService` (`../../services/frontendLoggingService`) | logging service | `debug`/`info`/`error` logging for preview init, reset trigger, URL changes, and image load/error events. |

### Upload mechanics & API call
- **File selection**: hidden native input `<input type="file" accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp">`; the visible button calls `fileInputRef.current?.click()`.
- **Validation (client-side)**: type must be in `['image/png', 'image/jpeg', 'image/jpg', 'image/webp']` and size must be ≤ 5 MB. Failures set `error`, rendered in an `alert alert-error`.
- **Preview**: `FileReader.readAsDataURL(file)` → `setPreview(result)`. No crop step.
- **Upload**: if `profileId` is set, `handleFileSelect` awaits `profileService.uploadProfileImage(profileId, file)`, which POSTs `FormData` (field `file`) to `POST /api/v1/agents/{profileId}/image` via `apiClient.upload`. The service reads `profile_image_url` (fallback `image_url`) from the `ImageUploadResponse`, keeps it **relative**, updates its internal profile cache, and returns the URL. On success `onImageUrlChange(imageUrl)` is called and the local file is cleared; on failure `error` is set and the local preview is kept.
- **Remove**: `handleRemoveImage` clears preview / local file / input value and calls `onImageUrlChange('')` + `onImageFileChange(null)`.
- **Reset**: effect on `resetTrigger` (> 0) clears `localFile`, interaction state, and the native input value.
- **Preview sync**: effect on `currentImageUrl` / `localFile` updates the preview from the parent unless a local file is selected (local preview takes precedence).

## Usage Example
```tsx
// Inside ProfileDetail, Basic Info tab
<ProfileImageUpload
  profileId={profile?.id}
  currentImageUrl={formData.image_url}
  onImageUrlChange={(url) => handleInputChange('image_url', url)}
  onImageFileChange={(file) => setSelectedImageFile(file)}
  isLoading={isSaving}
  resetTrigger={resetCounter}
/>
```

## State Used
| State | Type | Purpose |
|---|---|---|
| `preview` | `string \| null` | Data URL of the locally selected file, or the `currentImageUrl`; rendered as the thumbnail. |
| `uploading` | `boolean` | True while `profileService.uploadProfileImage` is in flight; shows the "Uploading image..." alert and disables controls. |
| `error` | `string \| null` | Validation or upload error message shown in an error alert. |
| `localFile` | `File \| null` | Currently selected file; used for deferred parent upload and preview precedence. |
| `hasInteracted` | `boolean` (setter only) | Tracks user interaction; the value is never read, only reset. |
| `fileInputRef` | `useRef<HTMLInputElement \| null>` | Ref to the hidden native file input for programmatic `.click()` and value clearing. |
| `pickerOpen` | `boolean` | Opens/closes the `ProfileImagePicker` store browser (the **Browse store** button). |

## Related Components
- `frontend/src/components/AgentProfiles/ProfileDetail.tsx` — the only consumer of `ProfileImageUpload`; renders it in the Basic Info tab, wires `onImageFileChange` into `selectedImageFile` for a deferred upload after create/update save, and drives `resetTrigger` when switching profiles.
- `frontend/src/pages/AgentProfiles.tsx` — page hosting `ProfileDetail`; also calls `profileService.uploadProfileImage()` directly after save when a pending image file exists.
- `frontend/src/services/domain/ProfileService.ts` — provides `uploadProfileImage()` (POST `/api/v1/agents/{profileId}/image`) and the `ImageUploadResponse` type.
- `frontend/src/services/frontendLoggingService.ts` — logging service used throughout the component.
