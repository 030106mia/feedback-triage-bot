"use client"

import { use } from "react"
import Link from "next/link"
import { AppLayout } from "@/components/app-layout"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { mockRules, mockEmail } from "@/lib/mock-data"
import { ArrowLeft, ArrowRight, Mail, FileText } from "lucide-react"

export default function PreviewPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params)
  const rule = mockRules.find((r) => r.id === resolvedParams.id)

  if (!rule) {
    return (
      <AppLayout>
        <div className="flex h-full items-center justify-center">
          <p className="text-muted-foreground">Rule not found</p>
        </div>
      </AppLayout>
    )
  }

  const jiraPreview = {
    summary: mockEmail.subject,
    description: mockEmail.body,
    project: rule.target.project,
    issueType: rule.target.issueType,
    reporter: mockEmail.sender,
  }

  return (
    <AppLayout>
      <div className="p-8">
        <div className="mb-8 flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href={`/rules/${resolvedParams.id}`}>
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-semibold text-foreground">Preview: {rule.name}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              See how an email will be converted into a Jira issue
            </p>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="border-border bg-card">
            <CardHeader className="border-b border-border">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                </div>
                <CardTitle className="text-lg">Email</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="border-b border-border p-4">
                <div className="space-y-2 text-sm">
                  <div className="flex items-baseline gap-2">
                    <span className="w-16 shrink-0 text-muted-foreground">From:</span>
                    <span className="font-medium text-foreground">
                      {mockEmail.senderName} {"<"}{mockEmail.sender}{">"}
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="w-16 shrink-0 text-muted-foreground">Subject:</span>
                    <span className="font-medium text-foreground">{mockEmail.subject}</span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="w-16 shrink-0 text-muted-foreground">Labels:</span>
                    <div className="flex gap-1.5">
                      {mockEmail.labels.map((label) => (
                        <span
                          key={label}
                          className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
              <div className="p-4">
                <pre className="whitespace-pre-wrap font-sans text-sm text-foreground">
                  {mockEmail.body}
                </pre>
              </div>
            </CardContent>
          </Card>

          <div className="flex flex-col">
            <div className="mb-4 hidden items-center justify-center lg:flex">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </div>
            </div>

            <Card className="flex-1 border-border bg-card">
              <CardHeader className="border-b border-border">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <CardTitle className="text-lg">Jira Issue</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="border-b border-border p-4">
                  <div className="space-y-3 text-sm">
                    <div className="flex items-baseline gap-2">
                      <span className="w-20 shrink-0 text-muted-foreground">Project:</span>
                      <span className="rounded bg-muted px-2 py-0.5 font-mono text-xs font-medium text-foreground">
                        {jiraPreview.project}
                      </span>
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className="w-20 shrink-0 text-muted-foreground">Type:</span>
                      <span className="font-medium text-foreground">{jiraPreview.issueType}</span>
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className="w-20 shrink-0 text-muted-foreground">Summary:</span>
                      <span className="font-medium text-foreground">{jiraPreview.summary}</span>
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className="w-20 shrink-0 text-muted-foreground">Reporter:</span>
                      <span className="text-foreground">{jiraPreview.reporter}</span>
                    </div>
                  </div>
                </div>
                <div className="p-4">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Description
                  </p>
                  <pre className="whitespace-pre-wrap font-sans text-sm text-foreground">
                    {jiraPreview.description}
                  </pre>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        <div className="mt-8 flex justify-end gap-3">
          <Button variant="outline" asChild>
            <Link href={`/rules/${resolvedParams.id}`}>Back to Rule</Link>
          </Button>
          <Button>Create Issue Now</Button>
        </div>
      </div>
    </AppLayout>
  )
}
