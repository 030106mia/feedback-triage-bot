"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { CheckCircle2, Mail, Zap } from "lucide-react"

export default function LandingPage() {
  const router = useRouter()
  const [gmailConnected, setGmailConnected] = useState(false)
  const [jiraConnected, setJiraConnected] = useState(false)

  const handleGmailConnect = () => {
    setGmailConnected(true)
  }

  const handleJiraConnect = () => {
    setJiraConnected(true)
  }

  const handleGetStarted = () => {
    router.push("/rules")
  }

  const bothConnected = gmailConnected && jiraConnected

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-8">
      <div className="w-full max-w-2xl">
        <div className="mb-12 text-center">
          <div className="mb-6 flex justify-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary">
              <Zap className="h-7 w-7 text-primary-foreground" />
            </div>
          </div>
          <h1 className="mb-3 text-3xl font-semibold tracking-tight text-foreground">
            Gmail to Jira Automation
          </h1>
          <p className="mx-auto max-w-md text-muted-foreground">
            Automatically convert selected Gmail emails into Jira issues through configurable rules. Reduce manual work and keep your team in sync.
          </p>
        </div>

        <div className="mb-8 grid gap-4 sm:grid-cols-2">
          <Card className="border-border bg-card">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                  <Mail className="h-5 w-5 text-muted-foreground" />
                </div>
                {gmailConnected && (
                  <CheckCircle2 className="h-5 w-5 text-success" />
                )}
              </div>
              <CardTitle className="text-lg">Connect Gmail</CardTitle>
              <CardDescription>
                Allow access to read your emails and apply automation rules
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                onClick={handleGmailConnect}
                variant={gmailConnected ? "secondary" : "default"}
                className="w-full"
                disabled={gmailConnected}
              >
                {gmailConnected ? "Connected" : "Connect Gmail"}
              </Button>
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                  <svg
                    className="h-5 w-5 text-muted-foreground"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path d="M11.53 2c-.59 0-1.18.22-1.63.67L2.67 9.91c-.9.9-.9 2.35 0 3.25l6.98 6.98c.9.9 2.35.9 3.25 0l7.23-7.23c.45-.45.67-1.04.67-1.63V4.8c0-1.54-1.26-2.8-2.8-2.8h-6.47zm.38 3.81c1.14 0 2.06.93 2.06 2.06 0 1.14-.93 2.06-2.06 2.06-1.14 0-2.06-.93-2.06-2.06 0-1.14.93-2.06 2.06-2.06z" />
                  </svg>
                </div>
                {jiraConnected && (
                  <CheckCircle2 className="h-5 w-5 text-success" />
                )}
              </div>
              <CardTitle className="text-lg">Connect Jira</CardTitle>
              <CardDescription>
                Allow access to create issues in your Jira projects
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                onClick={handleJiraConnect}
                variant={jiraConnected ? "secondary" : "default"}
                className="w-full"
                disabled={jiraConnected}
              >
                {jiraConnected ? "Connected" : "Connect Jira"}
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="text-center">
          <Button
            onClick={handleGetStarted}
            size="lg"
            disabled={!bothConnected}
            className="min-w-40"
          >
            Get Started
          </Button>
          {!bothConnected && (
            <p className="mt-3 text-sm text-muted-foreground">
              Connect both accounts to continue
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
