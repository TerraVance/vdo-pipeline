import { AlertCircle, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "./button"

interface ErrorBannerProps {
  message: string
  onRetry?: () => void
  retryLabel?: string
  className?: string
}

export function ErrorBanner({
  message,
  onRetry,
  retryLabel = "Retry",
  className,
}: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 p-4 rounded-xl",
        "bg-red-950/40 border border-red-500/30 text-red-300",
        className
      )}
    >
      <AlertCircle className="w-5 h-5 mt-0.5 shrink-0 text-red-400" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium leading-relaxed">{message}</p>
      </div>
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="shrink-0 border-red-500/40 text-red-300 hover:bg-red-500/10 hover:text-red-200"
        >
          <RefreshCw className="w-3 h-3 mr-1.5" />
          {retryLabel}
        </Button>
      )}
    </div>
  )
}
