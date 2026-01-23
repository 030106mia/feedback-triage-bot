"use client"

import { useState } from "react"
import Link from "next/link"
import { AppLayout } from "@/components/app-layout"
import { Button } from "@/components/ui/button"
import { RuleCard } from "@/components/rule-card"
import { EmptyState } from "@/components/empty-state"
import { mockRules } from "@/lib/mock-data"
import { Plus, List } from "lucide-react"

export default function RulesPage() {
  const [rules] = useState(mockRules)

  return (
    <AppLayout>
      <div className="p-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Rules</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Configure how emails are converted into Jira issues
            </p>
          </div>
          <Button asChild>
            <Link href="/rules/new">
              <Plus className="mr-2 h-4 w-4" />
              Create Rule
            </Link>
          </Button>
        </div>

        {rules.length === 0 ? (
          <EmptyState
            icon={List}
            title="No rules yet"
            description="Create your first automation rule to start converting emails into Jira issues."
            action={
              <Button asChild>
                <Link href="/rules/new">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Rule
                </Link>
              </Button>
            }
          />
        ) : (
          <div className="grid gap-4">
            {rules.map((rule) => (
              <RuleCard key={rule.id} rule={rule} />
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  )
}
