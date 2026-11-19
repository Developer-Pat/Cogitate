// Attachment preview for chat input
import { X, File, FileText, Image, FileCode, Sparkles } from 'lucide-react'

interface AttachmentPreviewProps {
  files: FileList | File[]
  onRemove: (index: number) => void
  onSummarize?: (index: number) => void
  uploadProgress?: number[]
}

// Map file extensions to icons
function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase()
  const imageExts = ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp']
  const codeExts = ['py', 'js', 'ts', 'jsx', 'tsx', 'json', 'yaml', 'yml']
  const docExts = ['md', 'txt', 'doc', 'docx', 'pdf']

  if (imageExts.includes(ext || '')) return Image
  if (codeExts.includes(ext || '')) return FileCode
  if (docExts.includes(ext || '')) return FileText
  return File
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function AttachmentPreview({ files, onRemove, onSummarize, uploadProgress }: AttachmentPreviewProps) {
  const fileArray = Array.from(files)

  if (fileArray.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2 px-3 pt-2 pb-1">
      {fileArray.map((file, index) => {
        const Icon = getFileIcon(file.name)
        const progress = uploadProgress?.[index]
        const isUploaded = progress === 100 || progress === undefined

        return (
          <div
            key={index}
            className="flex items-center gap-2 px-3 py-2 bg-[var(--chat-input-bg)] border border-[var(--chat-input-border)] rounded-lg max-w-[200px]"
          >
            <Icon className="w-4 h-4 flex-shrink-0 text-readout" />
            <div className="flex-1 min-w-0">
              <p className="text-xs truncate" title={file.name}>
                {file.name}
              </p>
              <p className="text-[10px] text-readout">
                {formatFileSize(file.size)}
              </p>
              {progress !== undefined && progress < 100 && (
                <div className="w-full bg-base-200 rounded-full h-1 mt-1">
                  <div
                    className="bg-primary h-1 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              )}
            </div>
            {/* Summarize button - triggers summary request */}
            {onSummarize && (
              <span className="tooltip tooltip-top" data-tip="Summarize this file">
              <button
                type="button"
                onClick={() => onSummarize(index)}
                className="text-readout hover:text-purple-500 transition-colors flex-shrink-0"
                aria-label="Summarize attachment"
              >
                <Sparkles className="w-3.5 h-3.5" />
              </button>
              </span>
            )}
            {isUploaded && (
              <button
                type="button"
                onClick={() => onRemove(index)}
                className="text-readout hover:text-error transition-colors flex-shrink-0"
                aria-label="Remove attachment"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
