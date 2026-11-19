/**
 * Collections Section Component
 * 
 * Section wrapper with title and count badge.
 */

import React, { type ReactNode } from 'react'

interface CollectionsSectionProps {
  title: string
  count: number
  viewMode: 'grid' | 'list'
  children: ReactNode
}

export const CollectionsSection: React.FC<CollectionsSectionProps> = ({
  title,
  count,
  viewMode,
  children,
}) => {
  const gridClasses = viewMode === 'grid'
    ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4'
    : 'flex flex-col gap-2'
  
  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <h2 className="text-lg font-semibold text-base-content">{title}</h2>
        <span className="text-sm text-readout bg-base-300/60 px-2 py-0.5 rounded-full">
          {count}
        </span>
      </div>
      <div className={gridClasses}>
        {children}
      </div>
    </section>
  )
}
