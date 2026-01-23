"use client"

import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/status-badge"
import type { Rule } from "@/lib/mock-data"
import { Tag, User, FileText, ArrowRight } from "lucide-react"

interface RuleCardProps {
  rule: Rule
}

const triggerIcons = {
  label: Tag,
  sender: User,
  keyword: FileText,
}

const triggerLabels = {
  label: "Label",
  sender: "Sender",
  keyword: "Keyword",
}

export function RuleCard({ rule }: RuleCardProps) {
  const TriggerIcon = triggerIcons[rule.trigger.type]

  return (
    <Link href={`/rules/${rule.id}`}>
      <Card className="border-border bg-card transition-colors hover:bg-accent/50">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between">
            <CardTitle className="text-base font-medium">{rule.name}</CardTitle>
            <StatusBadge status={rule.status} />
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <TriggerIcon className="h-3.5 w-3.5" />
              <span>
                {triggerLabels[rule.trigger.type]}: {rule.trigger.value}
              </span>
            </div>
            <ArrowRight className="h-3.5 w-3.5" />
            <span>
              {rule.target.project} / {rule.target.issueType}
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
