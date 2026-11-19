import React from 'react';

interface ToggleSwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  description?: string;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

/**
 * ToggleSwitch Component
 * 
 * Modern toggle switch with smooth animations
 */
export const ToggleSwitch: React.FC<ToggleSwitchProps> = ({
  checked,
  onChange,
  label,
  description,
  disabled = false,
  size = 'md'
}) => {
  const sizes = {
    sm: { toggle: 'w-10 h-5', circle: 'w-4 h-4', translate: 'translate-x-5' },
    md: { toggle: 'w-14 h-8', circle: 'w-6 h-6', translate: 'translate-x-6' },
    lg: { toggle: 'w-16 h-9', circle: 'w-7 h-7', translate: 'translate-x-7' }
  };

  const currentSize = sizes[size];

  return (
    <label className={`flex items-center gap-3 cursor-pointer ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}>
      <div className="relative">
        <input
          type="checkbox"
          className="sr-only"
          checked={checked}
          onChange={(e) => !disabled && onChange(e.target.checked)}
          disabled={disabled}
        />
        <div className={`block rounded-full transition-colors ${
          checked ? 'bg-success' : 'bg-base-300'
        } ${currentSize.toggle} ${disabled ? 'opacity-50' : ''}`}></div>
        <div className={`absolute bg-base-100 rounded-full transition-transform ${
          checked ? currentSize.translate : 'translate-x-0.5'
        } ${currentSize.circle} top-0.5 left-0.5`}></div>
      </div>
      
      {(label || description) && (
        <div className="flex flex-col">
          {label && (
            <span className={`text-sm font-medium ${
              disabled ? 'text-disabled' : 'text-base-content'
            }`}>
              {label}
            </span>
          )}
          {description && (
            <span className="text-xs text-readout">
              {description}
            </span>
          )}
        </div>
      )}
    </label>
  );
};

export default ToggleSwitch;
