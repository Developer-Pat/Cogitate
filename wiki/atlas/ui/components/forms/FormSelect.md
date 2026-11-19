---
title: FormSelect
type: atlas-component
path: frontend/src/components/forms/FormSelect.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# FormSelect

**Path**: `frontend/src/components/forms/FormSelect.tsx`
**Last Updated**: 2026-08-01

## Purpose
React Hook Form select dropdown — options list, optional placeholder ('Select...'), required marker, error styling, disabled state, help text.

## Props Interface
```typescript
export interface SelectOption { value: string; label: string }

export interface FormSelectProps {
  label: string
  name: string
  options: SelectOption[]
  placeholder?: string
  register: UseFormRegister<any>
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
<FormSelect label="Model" name="model" options={[{ value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' }]} register={register} error={errors.model} />
```

## State Used
None — controlled by react-hook-form via register.

## Related Components
- forms/FormInput.tsx, forms/FormCheckbox.tsx — sibling field components
- ui/settings/SettingsForm.tsx — form wrapper