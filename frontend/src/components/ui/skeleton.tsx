import { cn } from "@/lib/utils"

interface SkeletonProps {
  className?: string
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        "rounded-lg bg-white/5 animate-pulse relative overflow-hidden",
        "after:absolute after:inset-0 after:translate-x-[-100%]",
        "after:bg-gradient-to-r after:from-transparent after:via-white/5 after:to-transparent",
        "after:animate-[shimmer_1.5s_infinite]",
        className
      )}
    />
  )
}

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("space-y-3", className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn("h-4", i === lines - 1 ? "w-3/4" : "w-full")}
        />
      ))}
    </div>
  )
}

export function SkeletonImageGrid() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 w-full h-full">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="aspect-video rounded-xl w-full" />
      ))}
    </div>
  )
}
