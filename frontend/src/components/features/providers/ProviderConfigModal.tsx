/**
 * ProviderConfigModal Component - Phase 4
 *
 * Modal for adding/editing provider configurations.
 * Supports all provider types with API key management.
 */

import React, { useState, useEffect } from 'react';
import { useForm, type SubmitHandler } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import type { Resolver } from 'react-hook-form';
import type {
  ProviderConfig,
  ProviderConfigCreate,
  ProviderConfigUpdate,
} from '@/types/providers';
import { HelpButton } from '@/components/help/HelpButton';

/**
 * Configuration form schema using Zod
 */
const configFormSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Name too long'),
  display_name: z.string().max(100).optional(),
  provider_type: z.string().min(1, 'Provider type is required'),
  base_url: z.string().url('Invalid URL').optional().or(z.literal('')),
  api_key: z.string().optional(),
  is_active: z.boolean().default(true),
  priority: z.number().min(1).max(999).default(99),
});

type ConfigFormData = z.infer<typeof configFormSchema>;

interface ProviderConfigModalProps {
  provider: ProviderConfig | null;
  mode: 'add' | 'edit';
  onSave: (config: ProviderConfigCreate | ProviderConfigUpdate) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
  /** The class seam (2026-09-08, the A1 split): limits the
   * provider-type options to the page's class. */
  location?: 'cloud' | 'local';
}

/**
 * ProviderConfigModal Component
 */
const ProviderConfigModal: React.FC<ProviderConfigModalProps> = ({
  provider,
  mode,
  onSave,
  onCancel,
  loading = false,
  location,
}) => {
  const [showApiKey, setShowApiKey] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
    setValue,
  } = useForm<ConfigFormData>({
    resolver: zodResolver(configFormSchema) as unknown as Resolver<ConfigFormData>,
    mode: 'onChange',
    defaultValues: {
      name: '',
      display_name: '',
      provider_type: 'ollama',
      base_url: '',
      api_key: '',
      is_active: true,
      priority: 99,
    },
  });

  // Populate form when editing
  useEffect(() => {
    if (provider && mode === 'edit') {
      setValue('name', provider.name);
      setValue('display_name', provider.display_name || '');
      setValue('provider_type', provider.provider_type);
      setValue('base_url', provider.base_url || '');
      setValue('is_active', provider.is_active);
      setValue('priority', provider.priority);
    }
  }, [provider, mode, setValue]);

  /**
   * Handle form submission
   */
  const onSubmit = async (data: ConfigFormData) => {
    const config: ProviderConfigCreate | ProviderConfigUpdate = mode === 'add'
      ? {
          name: data.name,
          display_name: data.display_name || undefined,
          provider_type: data.provider_type,
          base_url: data.base_url || undefined,
          api_key: data.api_key || undefined,
          is_active: data.is_active,
          priority: data.priority,
        }
      : {
          display_name: data.display_name || undefined,
          base_url: data.base_url || undefined,
          api_key: data.api_key || undefined,
          is_active: data.is_active,
          priority: data.priority,
        };

    await onSave(config);
  };

  /**
   * Common provider types
   */
  // THE CLASS-AWARE TYPE LIST (2026-09-08, the A1 split): the
  // cloud page offers the SaaS types, the local page offers the
  // daemons. Unfiltered (no location prop) = the full list, for
  // any surface that still manages both classes together.
  const allProviderTypes = [
    { value: 'ollama', label: 'Ollama (Local)', location: 'local' as const },
    { value: 'llama', label: 'llama.cpp (Local)', location: 'local' as const },
    { value: 'ollama_cloud', label: 'Ollama Cloud', location: 'cloud' as const },
    { value: 'openai', label: 'OpenAI', location: 'cloud' as const },
    { value: 'anthropic', label: 'Anthropic', location: 'cloud' as const },
    { value: 'openrouter', label: 'OpenRouter', location: 'cloud' as const },
    { value: 'deepseek', label: 'Deepseek', location: 'cloud' as const },
    { value: 'groq', label: 'Groq', location: 'cloud' as const },
  ];
  const providerTypes = location
    ? allProviderTypes.filter(t => t.location === location)
    : allProviderTypes;

  return (
    <div
      className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-black/50"
      role="dialog"
      onClick={onCancel}
    >
      <div
        className="bg-base-100 rounded-box max-w-4xl w-full max-h-[90vh] overflow-y-auto shadow-xl p-6"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-base-content">
            {mode === 'add' ? 'Add Provider' : 'Edit Provider'}
          </h2>
          <div className="flex items-center gap-2">
            <HelpButton context="providers-config" size="sm" />
            <span className="tooltip tooltip-top" data-tip="Close">
            <button
              type="button"
              onClick={onCancel}
              className="btn btn-sm btn-circle btn-ghost"
              aria-label="Close"
              disabled={loading}
            >
              ✕
            </button>
            </span>
          </div>
        </div>

        {/* Form */}
        <form id="provider-config-form" onSubmit={handleSubmit(onSubmit as unknown as SubmitHandler<ConfigFormData>)} className="space-y-6">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-label  mb-2">
              Provider Name *
            </label>
            <input
              type="text"
              {...register('name')}
              disabled={mode === 'edit' || loading}
              className="w-full px-4 py-2 border border-base-content/20 dark:border-base-content/20 rounded-lg focus:ring-2 focus:ring-primary dark:bg-base-200 dark:text-base-content disabled:opacity-50"
              placeholder="e.g., openai, ollama"
            />
            {errors.name && (
              <p className="mt-1 text-sm text-error">{errors.name.message}</p>
            )}
          </div>

          {/* Display Name */}
          <div>
            <label className="block text-sm font-medium text-label  mb-2">
              Display Name
            </label>
            <input
              type="text"
              {...register('display_name')}
              disabled={loading}
              className="w-full px-4 py-2 border border-base-content/20 dark:border-base-content/20 rounded-lg focus:ring-2 focus:ring-primary dark:bg-base-200 dark:text-base-content disabled:opacity-50"
              placeholder="e.g., OpenAI (Cloud)"
            />
          </div>

          {/* Provider Type */}
          <div>
            <label className="block text-sm font-medium text-label  mb-2">
              Provider Type *
            </label>
            <select
              {...register('provider_type')}
              disabled={mode === 'edit' || loading}
              className="w-full px-4 py-2 border border-base-content/20 dark:border-base-content/20 rounded-lg focus:ring-2 focus:ring-primary dark:bg-base-200 dark:text-base-content disabled:opacity-50"
            >
              {providerTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
            {errors.provider_type && (
              <p className="mt-1 text-sm text-error">{errors.provider_type.message}</p>
            )}
          </div>

          {/* Base URL */}
          <div>
            <label className="block text-sm font-medium text-label  mb-2">
              Base URL
            </label>
            <input
              type="text"
              {...register('base_url')}
              disabled={loading}
              className="w-full px-4 py-2 border border-base-content/20 dark:border-base-content/20 rounded-lg focus:ring-2 focus:ring-primary dark:bg-base-200 dark:text-base-content disabled:opacity-50"
              placeholder="e.g., https://api.openai.com/v1"
            />
            {errors.base_url && (
              <p className="mt-1 text-sm text-error">{errors.base_url.message}</p>
            )}
          </div>

          {/* API Key */}
          <div>
            <label className="block text-sm font-medium text-label  mb-2">
              API Key
            </label>
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                {...register('api_key')}
                disabled={loading}
                className="w-full px-4 py-2 pr-12 border border-base-content/20 dark:border-base-content/20 rounded-lg focus:ring-2 focus:ring-primary dark:bg-base-200 dark:text-base-content disabled:opacity-50"
                placeholder="sk-..."
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-base-content/50 hover:text-base-content/70"
                tabIndex={-1}
              >
                {showApiKey ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 3.947-5.064 6.891-9.542 6.891-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
            <p className="mt-1 text-sm text-readout ">
              {mode === 'edit'
                ? (provider?.has_api_key
                    ? 'A key is already stored — leave blank to keep it, or enter a new one to replace it.'
                    : 'No key stored yet — enter one to enable this provider.')
                : 'Your API key will be encrypted'}
            </p>
          </div>

          {/* Priority */}
          <div>
            <label className="block text-sm font-medium text-label  mb-2">
              Priority (for fallback order)
            </label>
            <input
              type="number"
              {...register('priority', { valueAsNumber: true })}
              disabled={loading}
              className="w-full px-4 py-2 border border-base-content/20 dark:border-base-content/20 rounded-lg focus:ring-2 focus:ring-primary dark:bg-base-200 dark:text-base-content disabled:opacity-50"
              min="1"
              max="999"
            />
            <p className="mt-1 text-sm text-readout ">
              Lower number = higher priority in fallback chain
            </p>
          </div>

          {/* Active Toggle */}
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-label ">
              Provider Active
            </label>
            <input
              type="checkbox"
              {...register('is_active')}
              disabled={loading}
              className="w-5 h-5 text-primary border-base-content/20 rounded focus:ring-primary"
            />
          </div>

        </form>

        {/* Actions */}
        <div className="modal-action">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="btn btn-neutral btn-ghost"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="provider-config-form"
            disabled={loading || !isValid}
            className="btn btn-primary"
          >
            {loading ? 'Saving...' : mode === 'add' ? 'Add Provider' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProviderConfigModal;
