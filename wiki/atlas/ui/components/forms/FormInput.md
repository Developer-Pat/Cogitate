---
title: FormInput
type: atlas-component
path: frontend/src/components/forms/FormInput.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# FormInput

**Path**: `frontend/src/components/forms/FormInput.tsx`
**Last Updated**: 2026-08-01

## Purpose
React Hook Form text input field — supports text/email/password/number/url types, placeholder, required marker, error styling, disabled state, help text.

## Props Interface
```typescript
export interface FormInputProps {
  label: string
  name: string
  type?: 'text' | 'email' | 'password' | 'number' | 'url'  // default 'text'
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
<FormInput label="Provider API key" name="apiKey" type="password" register={register} error={errors.apiKey} required />
```

## State Used
None — controlled by react-hook-form via register.

## Related Components
- forms/FormCheckbox.tsx, forms/FormSelect.tsx — sibling field components
- ui/settings/SettingsForm.tsx — form wrapper