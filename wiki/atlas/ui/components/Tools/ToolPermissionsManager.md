---
title: Tool Permissions Manager
type: atlas-component
path: frontend/src/components/Tools/ToolPermissionsManager.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# Tool Permissions Manager

**Path**: `frontend/src/components/Tools/ToolPermissionsManager.tsx`
**Last Updated**: 2026-08-01

## Purpose

Full-screen modal for managing a single tool's access permissions. Implements a
**two-part permission model**:

1. **Default access level** — a tool-wide fallback applied to any user without an
   explicit collection permission.
2. **Per-collection permissions** — collection-specific overrides; each collection
   entry maps to exactly one permission level.

Permission levels (from `PERMISSION_LEVELS` in `types/toolPermissions.ts`):
`read` → `execute` → `write` → `admin`, plus `deny` (no access). Levels are ordered
by hierarchy (`deny` < `read` < `execute` < `write` < `admin`).

The modal loads the current permission snapshot on open, lets the user change
per-collection levels inline (each change is POSTed immediately), add/remove
collections, and persists everything with a final **Save Changes** action that PUTs
the full snapshot (default access + collection list) and notifies the parent.

Exported both as a named export (`export const ToolPermissionsManager`) and as the
default export.

## Props Interface

```typescript
interface ToolPermissionsManagerProps {
  toolId: string
  toolName: string
  onClose: () => void
  onPermissionsUpdated: () => void
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `toolPermissionsService` (`ToolPermissionsService`) | Service — `../../services/domain/ToolPermissionsService` | All API calls: fetch/update tool permissions, set/remove collection permissions, list collections without permissions |
| `useNotificationStore` | Store — `../../stores/notificationStore` | Success/error toast notifications for load/update/add/remove/save (accessed via `getState().addSuccess/addError`, not a hook) |
| `PermissionLevel`, `ToolPermissionsResponse` | Types — `../../types/toolPermissions` | Permission level union and API response typing |
| `PERMISSION_LEVELS` | Constant — `../../types/toolPermissions` | Per-level icon/label/description metadata for dropdowns and toasts |
| `CollectionPermissionRow` | Component — `./CollectionPermissionRow` | Renders one collection-permission table row (level dropdown badge, member count, remove button) |
| `PermissionBadge` | Component — `./PermissionBadge` | Badge for the default access level shown in the Access Summary |
| `useState`, `useEffect` | React hooks | Local state; initial load effect keyed on `toolId` |

## Usage Example

Rendered by `ToolsTableActions` when the "permissions" row action is clicked:

```tsx
import { ToolPermissionsManager } from './ToolPermissionsManager'
// ...
{showPermissionsManager && (
  <ToolPermissionsManager
    toolId={tool.id}
    toolName={tool.name}
    onClose={() => setShowPermissionsManager(false)}
    onPermissionsUpdated={handlePermissionsUpdated}
  />
)}
```

## State Used

| State | Type | Purpose |
|---|---|---|
| `isLoading` | `boolean` | Spinner overlay while permissions load on mount |
| `isSaving` | `boolean` | Disables footer buttons and shows spinner during Save |
| `permissions` | `ToolPermissionsResponse \| null` | Full permission payload (`default_access`, `permissions[]`, `total`) |
| `defaultAccess` | `PermissionLevel` (initial `'read'`) | Tool-wide default access level (set from response on load) |
| `showAddCollection` | `boolean` | Toggles the Add Collection form |
| `selectedCollectionId` | `string` | Currently selected collection in the Add form |
| `availableCollections` | `Array<{ id: string; name: string }>` | Collections without permissions yet — options for the Add dropdown |

On mount (effect keyed on `toolId`): `loadPermissions()` + `loadAvailableCollections()`
run in parallel.

## Flow

- **Load**: `GET /permissions` fills `permissions` + `defaultAccess`; available
  collections are fetched and filtered to those without permissions.
- **Change level inline**: row dropdown calls `handlePermissionChange` → POST
  `setCollectionPermission` → optimistic local state update (level + `updated_at`)
  → success toast.
- **Remove**: `window.confirm()` gate → DELETE `removeCollectionPermission` → local
  state filters the row and decrements `total` → success toast.
- **Add collection**: form select → `handleAddCollection` → POST at level `'read'`
  → reloads permissions + available collections, closes the form.
- **Save Changes**: `handleSave` → PUT `updateToolPermissions` with
  `{ default_access, permissions: [{ collection_id, permission_level }] }` →
  `onPermissionsUpdated()` then `onClose()`.

## API Endpoints

Called via `toolPermissionsService` (base path `/api/v1/tools`):

| Method | Endpoint | When |
|---|---|---|
| GET | `/api/v1/tools/{toolId}/permissions` | On mount (`loadPermissions`) |
| PUT | `/api/v1/tools/{toolId}/permissions` | Save Changes button (`handleSave`) |
| POST | `/api/v1/tools/{toolId}/permissions/collections/{collectionId}?permission_level={level}` | Inline level change; Add Collection (at `'read'`) |
| DELETE | `/api/v1/tools/{toolId}/permissions/collections/{collectionId}` | Remove button (after confirm) |
| GET | `/api/v1/collections?entity_type=tool` (via `CollectionsService.listCollections`, lazy-imported) | `getAvailableCollections` — fetches all tool collections, then filters out collections that already have permissions, client-side |

Notes:
- Inline row changes are POSTed immediately (optimistic local update), while the
  Save button pushes the entire snapshot via PUT — a full reload happens after
  add/remove before saving.
- `getAvailableCollections` is currently a frontend-side placeholder: the
  component comment notes "in real implementation, this would fetch collections
  that don't have permissions yet", and the service implements the filtering
  client-side over `listCollections`.
- The service also exposes `checkPermission` and `getAccessibleTools`, but these
  are **not** used by this modal.

## Related Components

- Parent: `frontend/src/components/Tools/ToolsTableActions.tsx` — renders the modal from row actions
- Sibling: `frontend/src/components/Tools/CollectionPermissionRow.tsx` — per-row UI (level dropdown, member count, remove)
- Sibling: `frontend/src/components/Tools/PermissionBadge.tsx` — default-access badge in the Access Summary
- Service: `frontend/src/services/domain/ToolPermissionsService.ts`
- Types: `frontend/src/types/toolPermissions.ts`
- API client: `frontend/src/services/apiClient.ts`
