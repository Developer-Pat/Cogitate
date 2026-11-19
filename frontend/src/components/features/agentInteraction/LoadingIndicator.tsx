import { useState, useEffect } from 'react'

interface LoadingIndicatorProps {
  size?: 'sm' | 'md' | 'lg'
  color?: string
}

export default function LoadingIndicator({ 
  size = 'md', 
  color = 'currentColor' 
}: LoadingIndicatorProps) {
  const [activeDot, setActiveDot] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveDot((prev) => (prev + 1) % 3)
    }, 300)

    return () => clearInterval(interval)
  }, [])

  const sizeClasses = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
    lg: 'w-4 h-4'
  }

  const containerClasses = {
    sm: 'gap-1',
    md: 'gap-1.5',
    lg: 'gap-2'
  }

  return (
    <div className={`flex items-center ${containerClasses[size]}`}>
      {[0, 1, 2].map((index) => (
        <div
          key={index}
          className={`${sizeClasses[size]} rounded-full transition-all duration-300 ease-in-out ${
            index === activeDot 
              ? 'bg-primary scale-125' 
              : 'bg-base-content/30 scale-100'
          }`}
          style={{
            backgroundColor: index === activeDot ? color : undefined,
          }}
        />
      ))}
    </div>
  )
}