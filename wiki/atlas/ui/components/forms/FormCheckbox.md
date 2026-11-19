---
title: FormCheckbox
type: atlas-component
path: frontend/src/components/forms/FormCheckbox.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# FormCheckbox

**Path**: `frontend/src/components/forms/FormCheckbox.tsx`
**Last Updated**: 2026-08-01

## Purpose
React Hook Form checkbox field — label, required marker, error styling, disabled state, and help text.

## Props Interface
```typescript
export interface FormCheckboxProps {
  label: string
  name: string
  register: UseFormRegister<any>   // react-hook-form
  error?: FieldError
  required?: boolean
  disabled?: boolean
  className?: string
  helpText?: string
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| UseFormRegister, FieldError | react-hook-form | Registration + validation errors |

## Usage Example
```tsx
<FormCheckbox label="Enable notifications" name="notify" register={register} error={errors.notify} />
```

## State Used
None — controlled by react-hook-form via register.

## Related Components
- forms/FormInput.tsx, forms/FormSelect.tsx — sibling field components
- ui/settings/SettingsForm.tsx — form wrapper injecting register/errors