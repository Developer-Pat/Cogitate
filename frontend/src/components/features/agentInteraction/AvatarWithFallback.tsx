import { useState } from 'react'

interface AvatarWithFallbackProps {
  src: string
  alt: string
  initials: string
  size: string
}

export function AvatarWithFallback({ src, alt, initials, size }: AvatarWithFallbackProps) {
  // THE PER-SRC FALLBACK (2026-09-08, the flicker): the one-shot
  // onError stuck the initials fallback FOREVER after a single
  // transient load failure (e.g. the backend-restart window when
  // /static briefly 404'd) — every store-driven remount then
  // flipped the avatar between the stuck fallback and the image
  // ("shows up then disappears"). The fallback is now keyed to the
  // src: a remount re-tries the load instead of trusting the old
  // failure, and a genuinely new src always starts from the image.
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const showFallback = failedSrc === src

  if (showFallback) {
    return (
      <div className={`${size} rounded-full bg-primary/20 text-primary flex items-center justify-center font-semibold`}>
        {initials}
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      className={`${size} rounded-full object-cover`}
      onError={() => setFailedSrc(src)}
    />
  )
}
