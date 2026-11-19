import React from 'react';

interface SkeletonLoaderProps {
  type?: 'card' | 'table' | 'text' | 'stat';
  count?: number;
  className?: string;
}

const SkeletonLoader: React.FC<SkeletonLoaderProps> = ({
  type = 'card',
  count = 1,
  className = ''
}) => {
  const renderSkeleton = () => {
    switch (type) {
      case 'card':
        return (
          <div className="card bg-base-100 shadow-xl animate-pulse shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
            <div className="card-body gap-[var(--card-gap)]">
              <div className="h-6 bg-base-300 rounded w-3/4 mb-4"></div>
              <div className="space-y-3">
                <div className="h-4 bg-base-300 rounded"></div>
                <div className="h-4 bg-base-300 rounded w-5/6"></div>
                <div className="h-4 bg-base-300 rounded w-4/6"></div>
              </div>
              <div className="card-actions justify-end mt-4">
                <div className="h-8 bg-base-300 rounded w-24"></div>
              </div>
            </div>
          </div>
        );

      case 'table':
        return (
          <div className="overflow-x-auto animate-pulse">
            <table className="table table-zebra w-full">
              <thead>
                <tr>
                  {[...Array(5)].map((_, i) => (
                    <th key={i}>
                      <div className="h-4 bg-base-300 rounded w-20"></div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...Array(5)].map((_, rowIndex) => (
                  <tr key={rowIndex}>
                    {[...Array(5)].map((_, cellIndex) => (
                      <td key={cellIndex}>
                        <div className="h-4 bg-base-300 rounded w-full"></div>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );

      case 'stat':
        return (
          <div className="stat bg-base-100 rounded-lg shadow animate-pulse">
            <div className="stat-figure">
              <div className="w-8 h-8 bg-base-300 rounded-full"></div>
            </div>
            <div className="stat-title">
              <div className="h-4 bg-base-300 rounded w-20"></div>
            </div>
            <div className="stat-value">
              <div className="h-8 bg-base-300 rounded w-16"></div>
            </div>
            <div className="stat-desc">
              <div className="h-3 bg-base-300 rounded w-24"></div>
            </div>
          </div>
        );

      case 'text':
      default:
        return (
          <div className="space-y-3 animate-pulse">
            <div className="h-4 bg-base-300 rounded"></div>
            <div className="h-4 bg-base-300 rounded w-5/6"></div>
            <div className="h-4 bg-base-300 rounded w-4/6"></div>
            <div className="h-4 bg-base-300 rounded w-3/4"></div>
          </div>
        );
    }
  };

  return (
    <div className={className}>
      {[...Array(count)].map((_, index) => (
        <div key={index} className={index > 0 ? 'mt-4' : ''}>
          {renderSkeleton()}
        </div>
      ))}
    </div>
  );
};

export default SkeletonLoader;