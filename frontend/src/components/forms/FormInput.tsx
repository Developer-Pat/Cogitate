import React from 'react';
import type { UseFormRegister, FieldError } from 'react-hook-form';

export interface FormInputProps {
  label: string;
  name: string;
  type?: 'text' | 'email' | 'password' | 'number' | 'url';
  placeholder?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  register: UseFormRegister<any>;
  error?: FieldError;
  required?: boolean;
  disabled?: boolean;
  className?: string;
  helpText?: string;
}

export const FormInput: React.FC<FormInputProps> = ({
  label,
  name,
  type = 'text',
  placeholder,
  register,
  error,
  required = false,
  disabled = false,
  className = '',
  helpText,
}) => {
  return (
    <div className={`form-control w-full ${className}`}>
      <label className="label" htmlFor={name}>
        <span className="label-text font-medium text-[var(--form-label-color)]" style={{ fontWeight: 'var(--form-label-font-weight)' }}>
          {label}
          {required && <span className="text-error ml-1">*</span>}
        </span>
      </label>

      <input
        id={name}
        type={type}
        placeholder={placeholder}
        className={`input input-bordered w-full ${
          error ? 'input-error' : ''
        } ${disabled ? 'input-disabled' : ''}`}
        style={{
          backgroundColor: 'var(--form-input-bg)',
          borderColor: 'var(--form-input-border)',
          color: 'var(--form-input-text)',
          borderRadius: 'var(--form-input-radius)',
          padding: 'var(--form-input-padding)'
        }}
        disabled={disabled}
        {...register(name, { required: required && `${label} is required` })}
      />

      {helpText && !error && (
        <label className="label">
          <span className="label-text-alt text-[var(--form-help-text-alt-color)]">{helpText}</span>
        </label>
      )}

      {error && (
        <label className="label">
          <span className="label-text-alt text-[var(--form-error-color)]">{error.message}</span>
        </label>
      )}
    </div>
  );
};

export default FormInput;