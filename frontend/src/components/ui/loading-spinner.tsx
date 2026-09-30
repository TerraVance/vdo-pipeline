import { cn } from "@/lib/utils"

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg"
  className?: string
  label?: string
}

const sizeMap = {
  sm: "w-4 h-4 border-2",
  md: "w-8 h-8 border-[3px]",
  lg: "w-16 h-16 border-[3px]",
}

export function LoadingSpinner({ size = "md", className, label }: LoadingSpinnerProps) {
  return (
    <div className={cn("flex flex-col items-center gap-3", className)}>
      <div
        className={cn(
          "rounded-full border-primary/30 border-t-primary animate-spin",
          sizeMap[size]
        )}
        role="status"
        aria-label={label || "Loading"}
      />
      {label && (
        <p className="text-sm font-medium text-primary animate-pulse">{label}</p>
      )}
    </div>
  )
}
