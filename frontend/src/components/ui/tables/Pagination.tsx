import React from 'react';

export interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems?: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  className?: string;
  showPageSizeOptions?: boolean;
  pageSizeOptions?: number[];
  showTotalItems?: boolean;
  showQuickJumper?: boolean;
}

export function Pagination({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  onPageSizeChange,
  className = '',
  showPageSizeOptions = true,
  pageSizeOptions = [10, 25, 50, 100],
  showTotalItems = true,
  showQuickJumper = false,
}: PaginationProps) {
  const canGoPrevious = currentPage > 1;
  const canGoNext = currentPage < totalPages;

  const handlePrevious = () => {
    if (canGoPrevious) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (canGoNext) {
      onPageChange(currentPage + 1);
    }
  };

  const handlePageSizeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newSize = parseInt(e.target.value, 10);
    onPageSizeChange?.(newSize);
  };

  const getPageNumbers = () => {
    const pages = [];
    const maxVisiblePages = 5;
    
    if (totalPages <= maxVisiblePages) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      const startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
      const endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
      
      if (startPage > 1) {
        pages.push(1);
        if (startPage > 2) {
          pages.push('...');
        }
      }
      
      for (let i = startPage; i <= endPage; i++) {
        pages.push(i);
      }
      
      if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
          pages.push('...');
        }
        pages.push(totalPages);
      }
    }
    
    return pages;
  };

  const renderPageButton = (page: number | string, index: number) => {
    if (page === '...') {
      return (
        <span
          key={`ellipsis-${index}`}
          className="px-3 py-2 text-sm text-readout "
        >
          ...
        </span>
      );
    }

    const pageNum = page as number;
    const isActive = pageNum === currentPage;

    return (
      <button
        key={pageNum}
        onClick={() => onPageChange(pageNum)}
        className={`
          px-3 py-2 text-sm font-medium border border-base-content/20 dark:border-base-content/20
          ${isActive
            ? 'bg-primary text-base-content border-primary'
            : 'bg-base-100 dark:bg-base-200 text-readout  hover:bg-base-200 dark:hover:bg-base-200'
          }
          transition-colors
        `}
      >
        {pageNum}
      </button>
    );
  };

  const startItem = totalItems ? (currentPage - 1) * pageSize + 1 : undefined;
  const endItem = totalItems ? Math.min(currentPage * pageSize, totalItems) : undefined;

  return (
    <div className={`flex flex-col sm:flex-row items-center justify-between space-y-4 sm:space-y-0 ${className}`}>
      {/* Page size selector and item count */}
      <div className="flex items-center space-x-4">
        {showPageSizeOptions && onPageSizeChange && (
          <div className="flex items-center space-x-2">
            <label htmlFor="page-size" className="text-sm text-readout ">
              Show:
            </label>
            <select
              id="page-size"
              value={pageSize}
              onChange={handlePageSizeChange}
              className="px-2 py-1 text-sm border border-base-content/20 dark:border-base-content/20 rounded bg-base-100 dark:bg-base-200 text-readout "
            >
              {pageSizeOptions.map(size => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </div>
        )}

        {showTotalItems && totalItems && (
          <div className="text-sm text-readout ">
            Showing {startItem} to {endItem} of {totalItems} items
          </div>
        )}
      </div>

      {/* Pagination controls */}
      <div className="flex items-center space-x-1">
        {/* Previous button */}
        <button
          onClick={handlePrevious}
          disabled={!canGoPrevious}
          className={`
            px-3 py-2 text-sm font-medium border border-base-content/20 dark:border-base-content/20 rounded-l
            ${canGoPrevious
              ? 'bg-base-100 dark:bg-base-200 text-readout  hover:bg-base-200 dark:hover:bg-base-200'
              : 'bg-base-200 dark:bg-base-200 text-disabled  cursor-not-allowed'
            }
            transition-colors
          `}
        >
          Previous
        </button>

        {/* Page numbers */}
        {getPageNumbers().map(renderPageButton)}

        {/* Next button */}
        <button
          onClick={handleNext}
          disabled={!canGoNext}
          className={`
            px-3 py-2 text-sm font-medium border border-base-content/20 dark:border-base-content/20 rounded-r
            ${canGoNext
              ? 'bg-base-100 dark:bg-base-200 text-readout  hover:bg-base-200 dark:hover:bg-base-200'
              : 'bg-base-200 dark:bg-base-200 text-disabled  cursor-not-allowed'
            }
            transition-colors
          `}
        >
          Next
        </button>
      </div>

      {/* Quick jumper */}
      {showQuickJumper && (
        <div className="flex items-center space-x-2">
          <span className="text-sm text-readout ">Go to:</span>
          <input
            type="number"
            min="1"
            max={totalPages}
            defaultValue={currentPage}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const target = e.target as HTMLInputElement;
                const page = parseInt(target.value, 10);
                if (page >= 1 && page <= totalPages) {
                  onPageChange(page);
                  target.value = '';
                }
              }
            }}
            className="w-16 px-2 py-1 text-sm border border-base-content/20 dark:border-base-content/20 rounded bg-base-100 dark:bg-base-200 text-readout "
          />
        </div>
      )}
    </div>
  );
}

// Server-side pagination hook
export interface UsePaginationProps {
  initialPage?: number;
  initialPageSize?: number;
  totalItems?: number;
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePagination({
  initialPage = 1,
  initialPageSize = 10,
  totalItems,
}: UsePaginationProps = {}) {
  const [currentPage, setCurrentPage] = React.useState(initialPage);
  const [pageSize, setPageSize] = React.useState(initialPageSize);

  const totalPages = totalItems ? Math.ceil(totalItems / pageSize) : 0;

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    setCurrentPage(1); // Reset to first page when page size changes
  };

  const getOffset = () => (currentPage - 1) * pageSize;

  return {
    currentPage,
    pageSize,
    totalPages,
    onPageChange: handlePageChange,
    onPageSizeChange: handlePageSizeChange,
    getOffset,
  };
}

export default Pagination;