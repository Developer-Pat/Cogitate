export function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      {/* Card skeleton */}
      <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <div className="flex justify-between items-center">
            <div className="h-6 bg-base-300 rounded w-1/4 animate-pulse"></div>
            <div className="h-8 bg-base-300 rounded w-20 animate-pulse"></div>
          </div>
          <div className="h-4 bg-base-300 rounded w-3/4 animate-pulse mt-2"></div>
          <div className="h-4 bg-base-300 rounded w-1/2 animate-pulse mt-1"></div>
        </div>
      </div>

      {/* Stats skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="stat bg-base-100 shadow-lg rounded-box">
            <div className="h-4 bg-base-300 rounded w-1/2 animate-pulse mb-2"></div>
            <div className="h-8 bg-base-300 rounded w-3/4 animate-pulse"></div>
          </div>
        ))}
      </div>

      {/* Table skeleton */}
      <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <div className="h-6 bg-base-300 rounded w-1/4 animate-pulse mb-4"></div>
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="flex items-center gap-4">
                <div className="h-4 bg-base-300 rounded w-16 animate-pulse"></div>
                <div className="h-4 bg-base-300 rounded flex-1 animate-pulse"></div>
                <div className="h-4 bg-base-300 rounded w-20 animate-pulse"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="overflow-x-auto">
      <table className="table table-zebra">
        <thead>
          <tr>
            <th><div className="h-4 bg-base-300 rounded w-24 animate-pulse"></div></th>
            <th><div className="h-4 bg-base-300 rounded w-16 animate-pulse"></div></th>
            <th><div className="h-4 bg-base-300 rounded w-20 animate-pulse"></div></th>
            <th><div className="h-4 bg-base-300 rounded w-32 animate-pulse"></div></th>
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, index) => (
            <tr key={index}>
              <td><div className="h-4 bg-base-300 rounded w-32 animate-pulse"></div></td>
              <td><div className="h-4 bg-base-300 rounded w-16 animate-pulse"></div></td>
              <td><div className="h-4 bg-base-300 rounded w-24 animate-pulse"></div></td>
              <td><div className="h-4 bg-base-300 rounded w-40 animate-pulse"></div></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function CardSkeleton() {
  return (
    <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
      <div className="card-body gap-[var(--card-gap)]">
        <div className="flex justify-between items-center">
          <div className="h-6 bg-base-300 rounded w-1/3 animate-pulse"></div>
          <div className="h-8 bg-base-300 rounded w-20 animate-pulse"></div>
        </div>
        <div className="space-y-2">
          <div className="h-4 bg-base-300 rounded w-full animate-pulse"></div>
          <div className="h-4 bg-base-300 rounded w-3/4 animate-pulse"></div>
          <div className="h-4 bg-base-300 rounded w-1/2 animate-pulse"></div>
        </div>
      </div>
    </div>
  )
}

export function StatsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="stat bg-base-100 shadow-lg rounded-box">
          <div className="h-4 bg-base-300 rounded w-1/2 animate-pulse mb-2"></div>
          <div className="h-8 bg-base-300 rounded w-3/4 animate-pulse"></div>
        </div>
      ))}
    </div>
  )
}