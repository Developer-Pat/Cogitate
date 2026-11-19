interface WorkflowTablePaginationProps {
  currentPage: number
  pageSize: number
  totalItems: number
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}

export default function WorkflowTablePagination({
  currentPage,
  pageSize,
  totalItems,
  onPageChange,
  onPageSizeChange
}: WorkflowTablePaginationProps) {
  const totalPages = Math.ceil(totalItems / pageSize)
  const startIndex = (currentPage - 1) * pageSize + 1
  const endIndex = Math.min(currentPage * pageSize, totalItems)

  const handlePageSizeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onPageSizeChange(Number(e.target.value))
  }

  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      onPageChange(page)
    }
  }

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

  if (totalItems === 0) return null

  return (
    <div className="p-4 border-t border-base-300 bg-base-100">
      <div className="flex items-center justify-between">
        {/* Items per page */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-readout">Show</span>
          <select
            value={pageSize}
            onChange={handlePageSizeChange}
            className="select select-bordered select-sm"
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
          <span className="text-sm text-readout">
            of {totalItems} items
          </span>
        </div>

        {/* Page info */}
        <div className="text-sm text-readout">
          Showing {startIndex} to {endIndex}
        </div>

        {/* Pagination controls */}
        <div className="flex items-center gap-1">
          {/* Previous button */}
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => goToPage(currentPage - 1)}
            disabled={currentPage === 1}
          >
            ‹
          </button>

          {/* Page numbers */}
          {getPageNumbers().map((page, index) => (
            <button
              key={index}
              className={`btn btn-sm ${
                page === currentPage ? 'btn-primary' : 'btn-ghost'
              }`}
              onClick={() => typeof page === 'number' && goToPage(page)}
              disabled={page === '...'}
            >
              {page}
            </button>
          ))}

          {/* Next button */}
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => goToPage(currentPage + 1)}
            disabled={currentPage === totalPages}
          >
            ›
          </button>
        </div>
      </div>
    </div>
  )
}
