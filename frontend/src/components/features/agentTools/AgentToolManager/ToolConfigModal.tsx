/**
 * ToolConfigModal Component
 * 
 * Modal for configuring tool settings with JSON Schema form generation.
 */

import React, { useState, useEffect } from 'react';
import type { AgentToolResponse } from '@/types/tools';
import { Info, Settings, X } from 'lucide-react';

export interface ToolConfigModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal is closed */
  onClose: () => void;
  /** Callback when configuration is saved */
  onSave: (toolId: string, config: unknown) => void;
  /** Agent tool data */
  agentTool: AgentToolResponse;
}

interface FormField {
  name: string;
  label: string;
  type: string;
  description?: string;
  default?: unknown;
  required: boolean;
  enum?: string[];
  minimum?: number;
  maximum?: number;
  pattern?: string;
  format?: string;
}

/**
 * ToolConfigModal Component
 */
export const ToolConfigModal: React.FC<ToolConfigModalProps> = ({
  isOpen,
  onClose,
  onSave,
  agentTool,
}) => {
  const [config, setConfig] = useState<Record<string, unknown>>(
    (agentTool.config as Record<string, unknown>) || {}
  );
  const [configJson, setConfigJson] = useState<string>('');
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'form' | 'json'>('form');
  const [formFields, setFormFields] = useState<FormField[]>([]);

  // Initialize form fields from JSON Schema
  useEffect(() => {
    if (agentTool.tool?.config_schema) {
      const schema = agentTool.tool.config_schema as Record<string, unknown>;
      const fields = generateFormFields(schema);
      setFormFields(fields);

      // Initialize config with defaults
      const initialConfig: Record<string, unknown> = {
        ...(agentTool.config as Record<string, unknown>),
      };
      fields.forEach(field => {
        if (field.default !== undefined && initialConfig[field.name] === undefined) {
          initialConfig[field.name] = field.default;
        }
      });
      setConfig(initialConfig);
      setConfigJson(JSON.stringify(initialConfig, null, 2));
    }
  }, [agentTool]);

  // Generate form fields from JSON Schema
  const generateFormFields = (schema: Record<string, unknown>): FormField[] => {
    if (!schema.properties || typeof schema.properties !== 'object') return [];

    const fields: FormField[] = [];
    const properties = schema.properties as Record<string, Record<string, unknown>>;
    const required = (schema.required as string[]) || [];

    Object.keys(properties).forEach(key => {
      const prop = properties[key];
      const field: FormField = {
        name: key,
        label: (prop.title as string) || key,
        type: (prop.type as string) || 'string',
        description: prop.description as string | undefined,
        default: prop.default,
        required: required.includes(key),
        enum: prop.enum as string[] | undefined,
        minimum: prop.minimum as number | undefined,
        maximum: prop.maximum as number | undefined,
        pattern: prop.pattern as string | undefined,
        format: prop.format as string | undefined,
      };
      fields.push(field);
    });

    return fields;
  };

  const handleFormChange = (fieldName: string, value: unknown) => {
    setConfig((prev: Record<string, unknown>) => ({
      ...prev,
      [fieldName]: value,
    }));

    // Update JSON representation
    const newConfig = { ...config, [fieldName]: value };
    setConfigJson(JSON.stringify(newConfig, null, 2));
  };

  const handleJsonChange = (value: string) => {
    setConfigJson(value);
    try {
      const parsed = JSON.parse(value) as Record<string, unknown>;
      setConfig(parsed);
      setJsonError(null);
    } catch {
      setJsonError('Invalid JSON');
    }
  };

  const handleSave = () => {
    onSave(agentTool.tool_id, config);
  };

  const renderFormField = (field: FormField) => {
    const value = config[field.name] !== undefined ? config[field.name] : field.default;

    switch (field.type) {
      case 'string':
        if (field.format === 'password') {
          return (
            <div key={field.name} className="mb-4">
              <label className="block text-sm font-medium text-base-content mb-1">
                {field.label}
                {field.required && <span className="text-error ml-1">*</span>}
              </label>
              <div className="tooltip tooltip-right" data-tip="Sensitive value - will be encrypted">
                <input
                  type="password"
                  value={(value as string) || ''}
                  onChange={(e) => handleFormChange(field.name, e.target.value)}
                  className="w-full px-3 py-2 border border-base-content/20 rounded bg-base-100 text-base-content focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder={field.description}
                  required={field.required}
                />
              </div>
              {field.description && (
                <p className="mt-1 text-sm text-readout">{field.description}</p>
              )}
            </div>
          );
        } else if (field.enum) {
          return (
            <div key={field.name} className="mb-4">
              <label className="block text-sm font-medium text-base-content mb-1">
                {field.label}
                {field.required && <span className="text-error ml-1">*</span>}
              </label>
              <select
                value={(value as string) || ''}
                onChange={(e) => handleFormChange(field.name, e.target.value)}
                className="w-full px-3 py-2 border border-base-content/20 rounded bg-base-100 text-base-content focus:outline-none focus:ring-2 focus:ring-primary"
                required={field.required}
              >
                <option value="">Select an option</option>
                {field.enum.map((option: string) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
              {field.description && (
                <p className="mt-1 text-sm text-readout">{field.description}</p>
              )}
            </div>
          );
        } else {
          return (
            <div key={field.name} className="mb-4">
              <label className="block text-sm font-medium text-base-content mb-1">
                {field.label}
                {field.required && <span className="text-error ml-1">*</span>}
              </label>
              <input
                type="text"
                value={(value as string) || ''}
                onChange={(e) => handleFormChange(field.name, e.target.value)}
                className="w-full px-3 py-2 border border-base-content/20 rounded bg-base-100 text-base-content focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder={field.description}
                required={field.required}
              />
              {field.description && (
                <p className="mt-1 text-sm text-readout">{field.description}</p>
              )}
            </div>
          );
        }

      case 'number':
      case 'integer':
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-base-content mb-1">
              {field.label}
              {field.required && <span className="text-error ml-1">*</span>}
            </label>
            <input
              type="number"
              value={value !== undefined ? (value as number) : ''}
              onChange={(e) => handleFormChange(field.name, e.target.value ? Number(e.target.value) : undefined)}
              min={field.minimum}
              max={field.maximum}
              className="w-full px-3 py-2 border border-base-content/20 rounded bg-base-100 text-base-content focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder={field.description}
              required={field.required}
            />
            {field.description && (
              <p className="mt-1 text-sm text-readout">{field.description}</p>
            )}
          </div>
        );

      case 'boolean':
        return (
          <div key={field.name} className="mb-4">
            <div className="flex items-center">
              <input
                type="checkbox"
                id={field.name}
                checked={!!value}
                onChange={(e) => handleFormChange(field.name, e.target.checked)}
                className="h-4 w-4 text-primary focus:ring-primary border-base-content/20 rounded"
              />
              <label htmlFor={field.name} className="ml-2 block text-sm text-base-content">
                {field.label}
                {field.required && <span className="text-error ml-1">*</span>}
              </label>
            </div>
            {field.description && (
              <p className="mt-1 text-sm text-readout ml-6">{field.description}</p>
            )}
          </div>
        );

      default:
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-base-content mb-1">
              {field.label}
            </label>
            <textarea
              value={value !== undefined ? JSON.stringify(value, null, 2) : ''}
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  handleFormChange(field.name, parsed);
                } catch {
                  // Keep as string if not valid JSON
                  handleFormChange(field.name, e.target.value);
                }
              }}
              className="w-full px-3 py-2 border border-base-content/20 rounded bg-base-100 text-base-content font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              rows={4}
              placeholder="Enter JSON or text..."
            />
            {field.description && (
              <p className="mt-1 text-sm text-readout">{field.description}</p>
            )}
          </div>
        );
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
        {/* Background overlay */}
        <div
          className="fixed inset-0 transition-opacity bg-black bg-opacity-50"
          onClick={onClose}
        ></div>

        {/* Modal panel */}
        <div className="inline-block align-bottom bg-base-100 rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full">
          <div className="px-6 pt-6 pb-4">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className="text-lg font-semibold text-base-content">
                  Configure {agentTool.tool?.name || 'Tool'}
                </h3>
                <p className="text-sm text-readout mt-1">
                  Customize tool settings for agent use
                </p>
              </div>
              <button
                onClick={onClose}
                className="text-base-content/60 hover:text-base-content"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Tabs */}
            <div className="border-b border-base-content/10 mb-4">
              <nav className="-mb-px flex space-x-8">
                <button
                  className={`py-2 px-1 border-b-2 font-medium text-sm ${activeTab === 'form' ? 'border-primary text-primary' : 'border-transparent text-base-content/60 hover:text-base-content hover:border-base-content/30'}`}
                  onClick={() => setActiveTab('form')}
                >
                  Form
                </button>
                <button
                  className={`py-2 px-1 border-b-2 font-medium text-sm ${activeTab === 'json' ? 'border-primary text-primary' : 'border-transparent text-base-content/60 hover:text-base-content hover:border-base-content/30'}`}
                  onClick={() => setActiveTab('json')}
                >
                  JSON Editor
                </button>
              </nav>
            </div>

            {/* Form content */}
            {activeTab === 'form' ? (
              <div>
                {formFields.length > 0 ? (
                  <div className="max-h-96 overflow-y-auto pr-2">
                    {formFields.map(field => renderFormField(field))}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <Settings className="h-10 w-10 mx-auto text-readout mb-4" />
                    <p className="text-readout">
                      This tool has no configuration options.
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div>
                <div className="mb-2">
                  <label className="block text-sm font-medium text-base-content mb-1">
                    Configuration JSON
                  </label>
                  <textarea
                    value={configJson}
                    onChange={(e) => handleJsonChange(e.target.value)}
                    className="w-full h-64 px-3 py-2 border border-base-content/20 rounded bg-base-100 text-base-content font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    spellCheck="false"
                  />
                  {jsonError && (
                    <p className="mt-1 text-sm text-error">{jsonError}</p>
                  )}
                </div>
                <div className="text-sm text-readout">
                  <p>
                    <Info className="h-4 w-4 inline-block mr-1 align-text-bottom" />
                    Edit the JSON configuration directly. Invalid JSON will be highlighted.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 bg-base-200 border-t border-base-content/10 flex justify-between">
            <div className="text-sm text-readout">
              Tool ID: <code className="ml-1 bg-base-300 px-1 py-0.5 rounded">{agentTool.tool_id}</code>
            </div>
            <div className="flex gap-2">
              <button
                onClick={onClose}
                className="btn btn-neutral btn-ghost btn-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="btn btn-primary btn-sm"
                disabled={!!jsonError}
              >
                Save Configuration
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
