"use client"

import { useState } from "react"
import { AppLayout } from "@/components/app-layout"
import { StatusBadge } from "@/components/status-badge"
import { EmptyState } from "@/components/empty-state"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { mockLogs } from "@/lib/mock-data"
import type { LogEntry } from "@/lib/mock-data"
import { FileText, ExternalLink, AlertCircle } from "lucide-react"

function formatDate(dateString: string) {
  const date = new Date(dateString)
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export default function LogsPage() {
  const [logs] = useState(mockLogs)
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null)

  return (
    <AppLayout>
      <div className="p-8">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-foreground">Logs</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            History of processed emails and their status
          </p>
        </div>

        {logs.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No logs yet"
            description="Logs will appear here once emails start being processed by your rules."
          />
        ) : (
          <div className="space-y-3">
            {logs.map((log) => (
              <Card
                key={log.id}
                className="border-border bg-card transition-colors hover:bg-accent/50"
              >
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-3">
                        <h3 className="truncate font-medium text-foreground">
                          {log.emailSubject}
                        </h3>
                        <StatusBadge status={log.status} />
                      </div>
                      <div className="mt-1 flex items-center gap-4 text-sm text-muted-foreground">
                        <span>{log.emailSender}</span>
                        <span className="text-border">|</span>
                        <span>Rule: {log.ruleName}</span>
                        <span className="text-border">|</span>
                        <span>{formatDate(log.timestamp)}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {log.jiraIssueKey && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-xs bg-transparent"
                          onClick={() =>
                            window.open(
                              `https://jira.example.com/browse/${log.jiraIssueKey}`,
                              "_blank"
                            )
                          }
                        >
                          {log.jiraIssueKey}
                          <ExternalLink className="ml-1.5 h-3 w-3" />
                        </Button>
                      )}
                      {log.status === "failed" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedLog(log)}
                        >
                          <AlertCircle className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        <Dialog open={!!selectedLog} onOpenChange={() => setSelectedLog(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Error Details</DialogTitle>
              <DialogDescription>
                Failed to process email: {selectedLog?.emailSubject}
              </DialogDescription>
            </DialogHeader>
            <div className="rounded-md border border-destructive/20 bg-destructive/10 p-4">
              <p className="text-sm text-destructive">{selectedLog?.error}</p>
            </div>
            <div className="text-sm text-muted-foreground">
              <p>
                <strong>Rule:</strong> {selectedLog?.ruleName}
              </p>
              <p>
                <strong>Time:</strong> {selectedLog && formatDate(selectedLog.timestamp)}
              </p>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  )
}
