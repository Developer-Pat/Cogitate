/**
 * WorkflowImport Component
 *
 * Component for importing workflow templates from files
 */

import React, { useState, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import type { WorkflowImportProps, WorkflowImportFormData, WorkflowImportData, WorkflowTemplate } from '@/types/workflows';
import { workflowImportFormSchema } from '@/types/workflows';

/**
 * Minimal template shape used for preview before full import.
 */
interface ParsedTemplate {
  name: string;
  description?: string;
  category?: string;
  steps?: unknown[];
  author?: string;
}

/**
 * WorkflowImport Component
 */
const WorkflowImport: React.FC<WorkflowImportProps> = ({
  onImport,
  onCancel,
  className: _className = ''
}) => {
  const [isImporting, setIsImporting] = useState<boolean>(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importedTemplate, setImportedTemplate] = useState<ParsedTemplate | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Form handling
  const {
    register,
    handleSubmit,
    formState: { errors: _errors },
    setValue: _setValue
  } = useForm<WorkflowImportFormData>({
    // @ts-expect-error - @hookform/resolvers v3 / react-hook-form v7 type incompatibility
    resolver: zodResolver(workflowImportFormSchema),
    defaultValues: {
      overwriteExisting: false,
      includeExecutions: false
    }
  });

  /**
   * Handle file selection
   */
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImportError(null);
    setImportedTemplate(null);

    // Validate file type
    if (!file.name.endsWith('.json') && !file.name.endsWith('.yaml') && !file.name.endsWith('.yml')) {
      setImportError('Please select a JSON or YAML file');
      return;
    }

    // Read and parse file
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const content = event.target?.result as string;
        let templateData: Record<string, unknown>;

        if (file.name.endsWith('.json')) {
          templateData = JSON.parse(content);
        } else {
          // For YAML files, we'd need a YAML parser
          // For now, we'll show an error since we don't have YAML parsing
          setImportError('YAML import is not yet supported. Please use JSON format.');
          return;
        }

        // Validate basic template structure
        if (!templateData.name || !templateData.steps || !Array.isArray(templateData.steps)) {
          setImportError('Invalid workflow template format. Missing required fields.');
          return;
        }

        setImportedTemplate(templateData as unknown as ParsedTemplate);
      } catch {
        setImportError('Failed to parse file. Please check the file format.');
      }
    };

    reader.onerror = () => {
      setImportError('Failed to read file.');
    };

    reader.readAsText(file);
  };

  /**
   * Handle form submission
   */
  const onSubmit = async (data: WorkflowImportFormData) => {
    if (!importedTemplate) {
      setImportError('Please select a valid workflow template file');
      return;
    }

    setIsImporting(true);
    setImportError(null);

    try {
      const importData: WorkflowImportData = {
        template: importedTemplate as unknown as WorkflowTemplate,
        overwriteExisting: data.overwriteExisting,
        includeExecutions: data.includeExecutions
      };

      await onImport(importData);
    } catch (error) {
      setImportError(error instanceof Error ? error.message : 'Import failed');
    } finally {
      setIsImporting(false);
    }
  };

  /**
   * Trigger file input click
   */
  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };



  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
        {/* Background overlay */}
        <div
          className="fixed inset-0 transition-opacity bg-black bg-opacity-50"
          onClick={onCancel}
          aria-hidden="true"
        ></div>

        {/* Modal panel */}
        <div className="inline-block align-bottom bg-base-100 rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full">
          {/* Header */}
          <div className="px-6 py-4 border-b border-base-content/20">
            <h2 className="text-lg font-semibold text-base-content">Import Workflow Template</h2>
            <p className="text-sm text-readout">Upload a workflow template file to import it into the system</p>
          </div>

      {/* Form */}
      {/* @ts-expect-error - @hookform/resolvers v3 / react-hook-form v7 type incompatibility */}
      <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-6">
        {/* File Upload */}
        <div>
          <label className="block text-sm font-medium text-label mb-2">
            Template File *
          </label>
          
          <div
            onClick={triggerFileInput}
            className="border-2 border-dashed border-base-content/20 rounded-lg p-6 text-center hover:border-base-content/20 transition-colors cursor-pointer"
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".json,.yaml,.yml"
              className="hidden"
            />
            
            <svg
              className="mx-auto h-12 w-12 text-readout"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            
            <div className="mt-4">
              <p className="text-sm font-medium text-base-content">
                {importedTemplate ? importedTemplate.name : 'Click to upload a file'}
              </p>
              <p className="text-sm text-readout">
                {importedTemplate 
                  ? `Template loaded: ${importedTemplate.steps?.length || 0} steps`
                  : 'Supported formats: JSON, YAML'
                }
              </p>
            </div>
          </div>

          {importError && (
            <p className="mt-2 text-sm text-error">{importError}</p>
          )}
        </div>

        {/* Template Preview */}
        {importedTemplate && (
          <div className="bg-base-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-base-content mb-3">Template Preview</h3>
            
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-readout">Name:</span>
                <span className="font-medium text-base-content">{importedTemplate.name}</span>
              </div>
              
              {importedTemplate.description && (
                <div className="flex justify-between">
                  <span className="text-readout">Description:</span>
                  <span className="font-medium text-base-content">{importedTemplate.description}</span>
                </div>
              )}
              
              <div className="flex justify-between">
                <span className="text-readout">Category:</span>
                <span className="font-medium text-base-content">{importedTemplate.category || 'Not specified'}</span>
              </div>
              
              <div className="flex justify-between">
                <span className="text-readout">Steps:</span>
                <span className="font-medium text-base-content">{importedTemplate.steps?.length || 0}</span>
              </div>
              
              <div className="flex justify-between">
                <span className="text-readout">Author:</span>
                <span className="font-medium text-base-content">{importedTemplate.author || 'Unknown'}</span>
              </div>
            </div>
          </div>
        )}

        {/* Import Options */}
        <div>
          <h3 className="text-sm font-medium text-base-content mb-3">Import Options</h3>
          
          <div className="space-y-3">
            {/* Overwrite Existing */}
            <div className="flex items-center">
              <input
                type="checkbox"
                id="overwriteExisting"
                {...register('overwriteExisting')}
                className="h-4 w-4 text-primary focus:ring-primary border-base-content/20 rounded"
              />
              <label htmlFor="overwriteExisting" className="ml-2 block text-sm text-base-content">
                Overwrite existing template if name matches
              </label>
            </div>

            {/* Include Executions */}
            <div className="flex items-center">
              <input
                type="checkbox"
                id="includeExecutions"
                {...register('includeExecutions')}
                className="h-4 w-4 text-primary focus:ring-primary border-base-content/20 rounded"
              />
              <label htmlFor="includeExecutions" className="ml-2 block text-sm text-base-content">
                Include execution history (if available)
              </label>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end space-x-3 pt-6 border-t border-base-content/20">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 border border-base-content/20 rounded-md shadow-sm text-sm font-medium text-base-content/90 bg-base-100 hover:bg-base-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
          >
            Cancel
          </button>
          
          <button
            type="submit"
            disabled={isImporting || !importedTemplate}
            className="inline-flex justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-base-content bg-primary hover:bg-info focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isImporting ? 'Importing...' : 'Import Template'}
          </button>
        </div>
      </form>
        </div>
      </div>
    </div>
  );
};

export default WorkflowImport;
