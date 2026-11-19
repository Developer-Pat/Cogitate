import { useState, useRef, useEffect } from 'react'
import { profileService } from '@/services/domain/ProfileService'
import type { Profile } from '@/services/domain/ProfileService'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import ProfileImagePicker from './ProfileImagePicker'
import ProfileHealthWidget from './ProfileHealthWidget'
import AgentServiceBadge from './AgentServiceBadge'

interface ProfileImageUploadProps {
  profileId?: string
  currentImageUrl?: string
  onImageUrlChange: (imageUrl: string) => void
  onImageFileChange?: (file: File | null) => void
  isLoading?: boolean
  resetTrigger?: number  // Increment this to reset the component
  /** The profile's provider health. The widget renders itself blank when absent. */
  health?: Profile['health'] | null
  /** Whether the profile's service can answer right now (G5-F2). Blank when nothing was checked. */
  serviceAvailability?: Profile['service_availability']
}

export default function ProfileImageUpload({
  profileId,
  currentImageUrl,
  onImageUrlChange,
  onImageFileChange,
  isLoading = false,
  resetTrigger = 0,
  health,
  serviceAvailability
}: ProfileImageUploadProps) {
  const [preview, setPreview] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [localFile, setLocalFile] = useState<File | null>(null)
  const [, setHasInteracted] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false)

  // Initialize preview with currentImageUrl on mount
  useEffect(() => {
    frontendLoggingService.debug('ProfileImageUpload', 'Initializing preview with currentImageUrl', {
      url: currentImageUrl,
      hasLocalFile: !!localFile,
      profileId
    })
    if (currentImageUrl) {
      frontendLoggingService.debug('ProfileImageUpload', 'Setting preview on mount', { url: currentImageUrl })
      setPreview(currentImageUrl)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Handle reset trigger (when parent clears selectedImageFile)
  useEffect(() => {
    frontendLoggingService.debug('ProfileImageUpload', 'Reset trigger received', { resetTrigger })
    if (resetTrigger > 0) {
      frontendLoggingService.debug('ProfileImageUpload', 'Clearing local file state')
      setLocalFile(null)
      setHasInteracted(false)
      // Clear file input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }, [resetTrigger])

  // Update preview when currentImageUrl changes (from parent component)
  useEffect(() => {
    frontendLoggingService.debug('ProfileImageUpload', 'currentImageUrl changed', { currentImageUrl, hasLocalFile: !!localFile })
    // Only update preview if we don't have a local file selected
    // (local file preview takes precedence)
    if (!localFile && currentImageUrl) {
      frontendLoggingService.debug('ProfileImageUpload', 'Updating preview to currentImageUrl', { url: currentImageUrl })
      setPreview(currentImageUrl)
      setHasInteracted(false) // Reset interaction state on profile change
    } else if (!localFile && !currentImageUrl) {
      frontendLoggingService.debug('ProfileImageUpload', 'currentImageUrl is empty and no local file, clearing preview')
      setPreview(null)
      setHasInteracted(false)
    }
    // If localFile exists, keep the local preview (don't override with currentImageUrl)
  }, [currentImageUrl, localFile])

  // Debug: log preview state changes
  useEffect(() => {
    frontendLoggingService.debug('ProfileImageUpload', 'Preview state changed', { preview, currentImageUrl, hasLocalFile: !!localFile })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview])

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setHasInteracted(true)

    // Validate file type
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp']
    if (!allowedTypes.includes(file.type)) {
      setError('Only PNG, JPEG, and WebP files are supported')
      return
    }

    // Validate file size (max 5MB)
    const maxSize = 5 * 1024 * 1024
    if (file.size > maxSize) {
      setError('File size must be less than 5MB')
      return
    }

    // Show preview
    const reader = new FileReader()
    reader.onload = (e) => {
      const result = e.target?.result as string
      setPreview(result)
      setError(null)
    }
    reader.readAsDataURL(file)

    // Track the file locally and for later upload
    setLocalFile(file)
    if (onImageFileChange) {
      onImageFileChange(file)
    }

    // Upload if profile exists
    if (profileId) {
      await uploadImage(file)
    }
  }

  const uploadImage = async (file: File) => {
    if (!profileId) {
      setError('Profile ID is required to upload image')
      return
    }

    try {
      setUploading(true)
      setError(null)
      const imageUrl = await profileService.uploadProfileImage(profileId, file)
      onImageUrlChange(imageUrl)
      // Clear local file after successful upload
      setLocalFile(null)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to upload image'
      setError(message)
      // Don't clear preview on error - keep the local file preview
    } finally {
      setUploading(false)
    }
  }

  const handleRemoveImage = () => {
    setPreview(null)
    setLocalFile(null)
    setHasInteracted(false)
    onImageUrlChange('')
    if (onImageFileChange) {
      onImageFileChange(null)
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="form-control w-full">
      <label className="label">
        <span className="label-text font-semibold">Profile Image</span>
      </label>

      <div className="flex gap-4">
        {/* Preview */}
        <div className="flex-shrink-0 group">
          {preview ? (
            <div className="relative">
              <img
                src={preview}
                alt="Profile preview"
                className="w-24 h-24 rounded-lg object-cover border-2 border-base-300"
                onError={(e) => {
                  frontendLoggingService.error('ProfileImageUpload', 'Image failed to load', new Error(`Failed to load: ${preview}`), { url: preview })
                  e.currentTarget.style.display = 'none'
                }}
                onLoad={() => frontendLoggingService.info('ProfileImageUpload', 'Image loaded successfully', { url: preview })}
              />
              <button
                type="button"
                onClick={handleRemoveImage}
                disabled={uploading || isLoading}
                className="absolute -top-2 -right-2 btn btn-xs btn-circle btn-error opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-0 tooltip tooltip-top"
                data-tip="Remove"
              >
                ✕
              </button>
            </div>
          ) : (
            <div className="w-24 h-24 rounded-lg border-2 border-dashed border-base-300 flex items-center justify-center bg-base-200">
              <span className="text-3xl">🖼️</span>
            </div>
          )}
        </div>

        {/* Upload Area */}
        <div className="flex-1 min-w-0">
          {/* Custom file picker button + the health widget.
              The buttons are NATURAL width now. As `flex-1` siblings they
              stretched to ~261px each — 522px for two actions — while the form
              fields below are only 320px wide, so most of this row was empty.
              That width now carries the health widget, which is the first
              thing the eye lands on in the tab. */}
          <div className="flex gap-2 items-start">
            {/* Hidden native file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
              onChange={handleFileSelect}
              disabled={uploading || isLoading}
              className="hidden"
            />
            {/* Upload file */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading || isLoading}
              className="btn btn-outline btn-sm tooltip tooltip-top"
              data-tip={localFile ? `Replace with ${localFile.name}` : (currentImageUrl ? `Current: ${currentImageUrl.split('/').pop()} — upload to replace` : 'Upload an image file (PNG, JPEG, WebP)')}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              Upload
            </button>
            {/* Browse store */}
            <button
              type="button"
              onClick={() => setPickerOpen(true)}
              disabled={uploading || isLoading}
              className="btn btn-outline btn-sm tooltip tooltip-top"
              data-tip="Choose from the image store (curated + uploads)"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
              Browse store
            </button>

            {/* Provider health — blank when there is nothing to report. */}
            <ProfileHealthWidget health={health} />
            {/* The CURRENT question beside the historical one (G5-F2): "can this agent run NOW?". */}
            <AgentServiceBadge availability={serviceAvailability} />
          </div>
          {error && (
            <div className="alert alert-error mt-2 py-2">
              <span className="text-sm">{error}</span>
            </div>
          )}

          {uploading && (
            <div className="alert alert-info mt-2 py-2">
              <span className="loading loading-spinner loading-sm"></span>
              <span className="text-sm">Uploading image...</span>
            </div>
          )}
        </div>
      </div>

      <ProfileImagePicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(url) => {
          onImageUrlChange(url)
          setPreview(url)
          setLocalFile(null)
          if (onImageFileChange) onImageFileChange(null)
          setPickerOpen(false)
          frontendLoggingService.info('ProfileImageUpload', 'Picked image from store', { url })
        }}
      />
    </div>
  )
}

