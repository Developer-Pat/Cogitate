import React from 'react';
import type { UseFormRegister, FieldError } from 'react-hook-form';

export interface FormCheckboxProps {
  label: string;
  name: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  register: UseFormRegister<any>;
  error?: FieldError;
  required?: boolean;
  disabled?: boolean;
  className?: string;
  helpText?: string;
}

export const FormCheckbox: React.FC<FormCheckboxProps> = ({
  label,
  name,
  register,
  error,
  required = false,
  disabled = false,
  className = '',
  helpText,
}) => {
  return (
    <div className={`form-control ${className}`}>
      <label className="label cursor-pointer justify-start gap-3">
        <input
          type="checkbox"
          className={`checkbox ${error ? 'checkbox-error' : 'checkbox-primary'} ${
            disabled ? 'checkbox-disabled' : ''
          }`}
          disabled={disabled}
          {...register(name, { required: required && `${label} is required` })}
        />
        <span className="label-text font-medium">
          {label}
          {required && <span className="text-error ml-1">*</span>}
        </span>
      </label>
      
      {helpText && !error && (
        <label className="label">
          <span className="label-text-alt text-readout ml-9">{helpText}</span>
        </label>
      )}
      
      {error && (
        <label className="label">
          <span className="label-text-alt text-error ml-9">{error.message}</span>
        </label>
      )}
    </div>
  );
};

export default FormCheckbox;