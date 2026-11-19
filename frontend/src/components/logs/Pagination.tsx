interface PaginationProps {
  currentPage: number
  totalPages: number
  totalItems: number
  pageSize: number
  hasPrevPage: boolean
  hasNextPage: boolean
  onPrevPage: () => void
  onNextPage: () => void
  onPageChange: (page: number) => void
}

export default function Pagination({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  hasPrevPage,
  hasNextPage,
  onPrevPage,
  onNextPage,
  onPageChange
}: PaginationProps) {
  const startItem = (currentPage - 1) * pageSize + 1
  const endItem = Math.min(currentPage * pageSize, totalItems)

  // Generate page numbers to display
  const getPageNumbers = () => {
    const pages: (number | string)[] = []
    const maxVisible = 5

    if (totalPages <= maxVisible) {
      // Show all pages
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      // Show first page
      pages.push(1)

      if (currentPage > 3) {
        pages.push('...')
      }

      // Show pages around current page
      for (let i = Math.max(2, currentPage - 1); i <= Math.min(totalPages - 1, currentPage + 1); i++) {
        if (!pages.includes(i)) {
          pages.push(i)
        }
      }

      if (currentPage < totalPages - 2) {
        pages.push('...')
      }

      // Show last page
      if (!pages.includes(totalPages)) {
        pages.push(totalPages)
      }
    }

    return pages
  }

  if (totalPages === 0) {
    return null
  }

  return (
    <div className="flex items-center justify-between flex-wrap gap-3">
      {/* Pagination controls */}
      <div className="flex items-center gap-2">
        {/* Previous button (2026-09-06: text-only — icons-XOR-text — with
            a DaisyUI tooltip replacing the native title) */}
        <span className="tooltip tooltip-top" data-tip={hasPrevPage ? 'Previous page' : 'Already on the first page'}>
          <button
            className={`btn btn-sm ${
              hasPrevPage
                ? 'btn-ghost cursor-pointer hover:scale-105'
                : 'btn-ghost cursor-not-allowed opacity-50'
            }`}
            onClick={onPrevPage}
            disabled={!hasPrevPage}
            aria-label="Previous page"
          >
            Prev
          </button>
        </span>

        {/* Page numbers */}
        <div className="flex items-center gap-1">
          {getPageNumbers().map((page, index) => (
            typeof page === 'number' ? (
              <button
                key={index}
                className={`btn btn-xs ${
                  currentPage === page
                    ? 'btn-primary'
                    : 'btn-ghost'
                }`}
                onClick={() => onPageChange(page)}
                aria-label={`Go to page ${page}`}
              >
                {page}
              </button>
            ) : (
              <span key={index} className="px-2 text-readout">
                {page}
              </span>
            )
          ))}
        </div>

        {/* Next button (2026-09-06: text-only + DaisyUI tooltip) */}
        <span className="tooltip tooltip-top" data-tip={hasNextPage ? 'Next page' : 'Already on the last page'}>
          <button
            className={`btn btn-sm ${
              hasNextPage
                ? 'btn-ghost cursor-pointer hover:scale-105'
                : 'btn-ghost cursor-not-allowed opacity-50'
            }`}
            onClick={onNextPage}
            disabled={!hasNextPage}
            aria-label="Next page"
          >
            Next
          </button>
        </span>
      </div>

      {/* Log count display */}
      <div className="text-sm text-readout">
        {totalItems > 0 ? (
          <>
            Showing <span className="font-semibold text-base-content">{startItem}-{endItem}</span> of{' '}
            <span className="font-semibold text-base-content">{totalItems}</span> logs
          </>
        ) : (
          <span>No logs found</span>
        )}
      </div>
    </div>
  )
}
