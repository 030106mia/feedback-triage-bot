"use client"

import { useState, use } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { AppLayout } from "@/components/app-layout"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { mockRules, mockProjects, mockIssueTypes } from "@/lib/mock-data"
import { ArrowLeft, Trash2, Eye } from "lucide-react"

export default function RuleEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params)
  const router = useRouter()
  const isNew = resolvedParams.id === "new"
  const existingRule = mockRules.find((r) => r.id === resolvedParams.id)

  const [name, setName] = useState(existingRule?.name || "")
  const [isActive, setIsActive] = useState(existingRule?.status === "active")
  const [triggerType, setTriggerType] = useState<"label" | "sender" | "keyword">(
    existingRule?.trigger.type || "label"
  )
  const [triggerValue, setTriggerValue] = useState(existingRule?.trigger.value || "")
  const [project, setProject] = useState(existingRule?.target.project || "")
  const [issueType, setIssueType] = useState(existingRule?.target.issueType || "")
  const [behavior, setBehavior] = useState<"auto-create" | "create-draft" | "manual-review">(
    existingRule?.behavior || "auto-create"
  )

  const handleSave = () => {
    router.push("/rules")
  }

  const handleDelete = () => {
    router.push("/rules")
  }

  return (
    <AppLayout>
      <div className="p-8">
        <div className="mb-8 flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/rules">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-semibold text-foreground">
              {isNew ? "Create Rule" : "Edit Rule"}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {isNew
                ? "Configure how emails will be converted to Jira issues"
                : "Modify your automation rule settings"}
            </p>
          </div>
          {!isNew && (
            <Button variant="outline" asChild>
              <Link href={`/rules/${resolvedParams.id}/preview`}>
                <Eye className="mr-2 h-4 w-4" />
                Preview
              </Link>
            </Button>
          )}
        </div>

        <div className="mx-auto max-w-2xl space-y-6">
          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-lg">Basic Info</CardTitle>
              <CardDescription>Name your rule and set its status</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Rule Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Support Tickets"
                />
              </div>
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Rule Status</Label>
                  <p className="text-sm text-muted-foreground">
                    {isActive ? "Rule is active and processing emails" : "Rule is paused"}
                  </p>
                </div>
                <Switch checked={isActive} onCheckedChange={setIsActive} />
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-lg">Gmail Trigger</CardTitle>
              <CardDescription>Define which emails will trigger this rule</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Trigger Type</Label>
                <Select
                  value={triggerType}
                  onValueChange={(v) => setTriggerType(v as typeof triggerType)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="label">Gmail Label</SelectItem>
                    <SelectItem value="sender">Sender Email/Domain</SelectItem>
                    <SelectItem value="keyword">Keyword in Subject</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="triggerValue">
                  {triggerType === "label" && "Label Name"}
                  {triggerType === "sender" && "Email or Domain"}
                  {triggerType === "keyword" && "Keyword"}
                </Label>
                <Input
                  id="triggerValue"
                  value={triggerValue}
                  onChange={(e) => setTriggerValue(e.target.value)}
                  placeholder={
                    triggerType === "label"
                      ? "e.g., Support"
                      : triggerType === "sender"
                        ? "e.g., @enterprise.com"
                        : "e.g., bug report"
                  }
                />
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-lg">Jira Target</CardTitle>
              <CardDescription>Select where issues will be created</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Project</Label>
                <Select value={project} onValueChange={setProject}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a project" />
                  </SelectTrigger>
                  <SelectContent>
                    {mockProjects.map((p) => (
                      <SelectItem key={p.id} value={p.key}>
                        {p.name} ({p.key})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Issue Type</Label>
                <Select value={issueType} onValueChange={setIssueType}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select an issue type" />
                  </SelectTrigger>
                  <SelectContent>
                    {mockIssueTypes.map((t) => (
                      <SelectItem key={t.id} value={t.name}>
                        {t.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-lg">Field Mapping</CardTitle>
              <CardDescription>How email content maps to Jira fields</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-md border border-border bg-muted/50 px-4 py-3">
                  <span className="text-sm text-muted-foreground">Email Subject</span>
                  <span className="text-sm font-medium text-foreground">Jira Summary</span>
                </div>
                <div className="flex items-center justify-between rounded-md border border-border bg-muted/50 px-4 py-3">
                  <span className="text-sm text-muted-foreground">Email Body</span>
                  <span className="text-sm font-medium text-foreground">Jira Description</span>
                </div>
                <div className="flex items-center justify-between rounded-md border border-border bg-muted/50 px-4 py-3">
                  <span className="text-sm text-muted-foreground">Sender Email</span>
                  <span className="text-sm font-medium text-foreground">Reporter Field</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-lg">Behavior</CardTitle>
              <CardDescription>What happens when an email matches this rule</CardDescription>
            </CardHeader>
            <CardContent>
              <Select value={behavior} onValueChange={(v) => setBehavior(v as typeof behavior)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto-create">Auto-create issue</SelectItem>
                  <SelectItem value="create-draft">Create as draft</SelectItem>
                  <SelectItem value="manual-review">Require manual review</SelectItem>
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          <div className="flex items-center justify-between pt-4">
            {!isNew && (
              <Button variant="destructive" onClick={handleDelete}>
                <Trash2 className="mr-2 h-4 w-4" />
                Delete Rule
              </Button>
            )}
            <div className={`flex gap-3 ${isNew ? "ml-auto" : ""}`}>
              <Button variant="outline" asChild>
                <Link href="/rules">Cancel</Link>
              </Button>
              <Button onClick={handleSave}>Save Rule</Button>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
