/**
 * WorkflowEditor Component
 * 
 * Component for editing and customizing workflow templates
 */

import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import type { WorkflowEditorProps, WorkflowTemplateFormData } from '@/types/workflows';
import { workflowTemplateFormSchema } from '@/types/workflows';

/**
 * WorkflowEditor Component
 */
const WorkflowEditor: React.FC<WorkflowEditorProps> = ({
  template,
  onSave,
  onCancel,
  onValidate,
  className: _className = ''
}) => {
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);

  // Form handling
  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
    watch,
    setValue
  } = useForm<WorkflowTemplateFormData>({
    // @ts-expect-error - @hookform/resolvers v3 types incompatible with react-hook-form v7 resolver type
    resolver: zodResolver(workflowTemplateFormSchema as unknown),
    defaultValues: {
      name: template.name,
      description: template.description,
      category: template.category,
      tags: template.tags,
      isPublic: template.isPublic,
      isCustomizable: template.isCustomizable
    }
  });

  /**
   * Handle form submission
   */
  const onSubmit = async (data: WorkflowTemplateFormData) => {
    setIsValidating(true);
    setValidationErrors([]);
    setValidationWarnings([]);

    try {
      // Create updated template
      const updatedTemplate = {
        ...template,
        ...data,
        updatedAt: new Date().toISOString()
      };

      // Validate the template
      const validationResult = await onValidate(updatedTemplate);
      
      if (validationResult) {
        onSave(updatedTemplate);
      } else {
        setValidationErrors(['Template validation failed']);
      }
    } catch (error) {
      setValidationErrors([error instanceof Error ? error.message : 'Validation failed']);
    } finally {
      setIsValidating(false);
    }
  };

  /**
   * Handle cancel
   */
  const handleCancel = () => {
    if (isDirty) {
      const confirmed = window.confirm('You have unsaved changes. Are you sure you want to cancel?');
      if (!confirmed) return;
    }
    onCancel();
  };

  /**
   * Handle tag input
   */
  const handleTagInput = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && e.currentTarget.value.trim()) {
      e.preventDefault();
      const newTag = e.currentTarget.value.trim();
      const currentTags = watch('tags') || [];
      
      if (!currentTags.includes(newTag)) {
        setValue('tags', [...currentTags, newTag], { shouldDirty: true });
        e.currentTarget.value = '';
      }
    }
  };

  /**
   * Remove tag
   */
  const removeTag = (tagToRemove: string) => {
    const currentTags = watch('tags') || [];
    setValue('tags', currentTags.filter(tag => tag !== tagToRemove), { shouldDirty: true });
  };

  const currentTags = watch('tags') || [];

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
        <div className="inline-block align-bottom bg-base-100 rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-3xl sm:w-full">
          {/* Header */}
          <div className="px-6 py-4 border-b border-base-content/20">
            <h2 className="text-lg font-semibold text-base-content">Edit Workflow Template</h2>
            <p className="text-sm text-readout">Modify basic metadata (name, description, category, tags)</p>
          </div>

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit as unknown as (data: WorkflowTemplateFormData) => Promise<void>)} className="p-6 space-y-6">
        {/* Basic Information */}
        <div>
          <h3 className="text-md font-medium text-base-content mb-4">Basic Information</h3>
          
          <div className="grid grid-cols-1 gap-4">
            {/* Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-label mb-1">
                Name *
              </label>
              <input
                type="text"
                id="name"
                {...register('name')}
                className="input input-bordered w-full"
                placeholder="Enter workflow name"
              />
              {errors.name && (
                <p className="mt-1 text-sm text-error">{errors.name.message}</p>
              )}
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-label mb-1">
                Description *
              </label>
              <textarea
                id="description"
                rows={3}
                {...register('description')}
                className="textarea textarea-bordered w-full"
                placeholder="Describe the workflow purpose and functionality"
              />
              {errors.description && (
                <p className="mt-1 text-sm text-error">{errors.description.message}</p>
              )}
            </div>

            {/* Category */}
            <div>
              <label htmlFor="category" className="block text-sm font-medium text-label mb-1">
                Category *
              </label>
              <input
                type="text"
                id="category"
                {...register('category')}
                className="input input-bordered w-full"
                placeholder="e.g., Research, Analysis, Automation"
              />
              {errors.category && (
                <p className="mt-1 text-sm text-error">{errors.category.message}</p>
              )}
            </div>

            {/* Tags */}
            <div>
              <label htmlFor="tags" className="block text-sm font-medium text-label mb-1">
                Tags
              </label>
              <div className="flex flex-wrap gap-2 mb-2">
                {currentTags.map((tag, index) => (
                  <span
                    key={index}
                    className="inline-flex items-center px-2 py-1 rounded-md text-sm bg-primary/10 text-primary"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="ml-1 text-primary hover:text-primary/80"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <input
                type="text"
                id="tags"
                onKeyDown={handleTagInput}
                className="input input-bordered w-full"
                placeholder="Type a tag and press Enter to add"
              />
            </div>
          </div>
        </div>

        {/* Settings */}
        <div>
          <h3 className="text-md font-medium text-base-content mb-4">Settings</h3>
          
          <div className="space-y-4">
            {/* Public/Private */}
            <div className="flex items-center">
              <input
                type="checkbox"
                id="isPublic"
                {...register('isPublic')}
                className="checkbox checkbox-sm checkbox-primary"
              />
              <label htmlFor="isPublic" className="ml-2 block text-sm text-base-content">
                Make this template public
              </label>
            </div>

            {/* Customizable */}
            <div className="flex items-center">
              <input
                type="checkbox"
                id="isCustomizable"
                {...register('isCustomizable')}
                className="checkbox checkbox-sm checkbox-primary"
              />
              <label htmlFor="isCustomizable" className="ml-2 block text-sm text-base-content">
                Allow customization by other users
              </label>
            </div>
          </div>
        </div>

        {/* Validation Results */}
        {(validationErrors.length > 0 || validationWarnings.length > 0) && (
          <div className="space-y-3">
            {validationErrors.length > 0 && (
              <div className="alert alert-error text-sm">
                <h4 className="font-medium">Validation Errors</h4>
                <ul className="list-disc list-inside space-y-1">
                  {validationErrors.map((error, index) => (
                    <li key={index}>{error}</li>
                  ))}
                </ul>
              </div>
            )}
            
            {validationWarnings.length > 0 && (
              <div className="alert alert-warning text-sm">
                <h4 className="font-medium">Validation Warnings</h4>
                <ul className="list-disc list-inside space-y-1">
                  {validationWarnings.map((warning, index) => (
                    <li key={index}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end space-x-3 pt-6 border-t border-base-content/20">
          <button
            type="button"
            onClick={handleCancel}
            className="btn btn-neutral btn-ghost"
          >
            Cancel
          </button>
          
          <button
            type="submit"
            disabled={isValidating || !isDirty}
            className="btn btn-primary"
          >
            {isValidating ? 'Validating...' : 'Save Changes'}
          </button>
        </div>
      </form>
        </div>
      </div>
    </div>
  );
};

export default WorkflowEditor;