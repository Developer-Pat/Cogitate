import React from 'react';
import type { UseFormRegister, FieldError } from 'react-hook-form';

export interface SelectOption {
  value: string;
  label: string;
}

export interface FormSelectProps {
  label: string;
  name: string;
  options: SelectOption[];
  placeholder?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  register: UseFormRegister<any>;
  error?: FieldError;
  required?: boolean;
  disabled?: boolean;
  className?: string;
  helpText?: string;
}

export const FormSelect: React.FC<FormSelectProps> = ({
  label,
  name,
  options,
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
        <span className="label-text font-medium">
          {label}
          {required && <span className="text-error ml-1">*</span>}
        </span>
      </label>
      
      <select
        id={name}
        className={`select select-bordered w-full ${
          error ? 'select-error' : ''
        } ${disabled ? 'select-disabled' : ''}`}
        disabled={disabled}
        {...register(name, { required: required && `${label} is required` })}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      
      {helpText && !error && (
        <label className="label">
          <span className="label-text-alt text-readout">{helpText}</span>
        </label>
      )}
      
      {error && (
        <label className="label">
          <span className="label-text-alt text-error">{error.message}</span>
        </label>
      )}
    </div>
  );
};

export default FormSelect;