import { cn } from "@/lib/utils"

interface StatusBadgeProps {
  status: "active" | "paused" | "success" | "failed" | "pending"
  className?: string
}

const statusStyles = {
  active: "bg-success/15 text-success",
  paused: "bg-muted text-muted-foreground",
  success: "bg-success/15 text-success",
  failed: "bg-destructive/15 text-destructive",
  pending: "bg-warning/15 text-warning",
}

const statusLabels = {
  active: "Active",
  paused: "Paused",
  success: "Success",
  failed: "Failed",
  pending: "Pending",
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        statusStyles[status],
        className
      )}
    >
      <span className={cn(
        "mr-1.5 h-1.5 w-1.5 rounded-full",
        status === "active" || status === "success" ? "bg-success" : "",
        status === "paused" ? "bg-muted-foreground" : "",
        status === "failed" ? "bg-destructive" : "",
        status === "pending" ? "bg-warning" : ""
      )} />
      {statusLabels[status]}
    </span>
  )
}
