import React, { useState } from 'react'
import { collectionsService } from '@/services/domain/CollectionsService'

interface Collection {
  id: string
  name: string
  icon: string
  item_count: number
}

/**
 * Collections Badges Component
 * Shows which collections contain this profile/agent
 */
export default function CollectionsBadges({ profileId }: { profileId: string }) {
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)

  // Update when profileId changes
  React.useEffect(() => {
    const updateCollections = async () => {
      try {
        setLoading(true)
        const result = await collectionsService.findCollectionsContainingEntity('agent', profileId)
        setCollections(result.collections)
      } catch (error) {
        console.error('Failed to load collections for profile:', error)
        setCollections([])
      } finally {
        setLoading(false)
      }
    }
    updateCollections()
  }, [profileId])

  if (loading) return null
  if (collections.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {collections.slice(0, 3).map(collection => (
        <span
          key={collection.id}
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-primary/10 text-primary border border-primary/20"
          data-tip={collection.name}
        >
          <span>{collection.icon}</span>
        </span>
      ))}
      {collections.length > 3 && (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-base-200 text-readout border border-base-content/20">
          +{collections.length - 3}
        </span>
      )}
    </div>
  )
}
