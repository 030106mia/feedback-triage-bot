"use client"

import { useState } from "react"
import { AppLayout } from "@/components/app-layout"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { CheckCircle2, Mail, AlertTriangle } from "lucide-react"

export default function SettingsPage() {
  const [emailNotifications, setEmailNotifications] = useState(true)
  const [autoRetry, setAutoRetry] = useState(true)

  return (
    <AppLayout>
      <div className="p-8">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-foreground">Settings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage your account connections and preferences
          </p>
        </div>

        <div className="mx-auto max-w-2xl space-y-6">
          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-lg">Connected Accounts</CardTitle>
              <CardDescription>Manage your Gmail and Jira connections</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between rounded-md border border-border p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                    <Mail className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="font-medium text-foreground">Gmail</p>
                    <p className="text-sm text-muted-foreground">john@example.com</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="h-5 w-5 text-success" />
                  <Button variant="outline" size="sm">
                    Disconnect
                  </Button>
                </div>
              </div>

              <div className="flex items-center justify-between rounded-md border border-border p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                    <svg
                      className="h-5 w-5 text-muted-foreground"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                    >
                      <path d="M11.53 2c-.59 0-1.18.22-1.63.67L2.67 9.91c-.9.9-.9 2.35 0 3.25l6.98 6.98c.9.9 2.35.9 3.25 0l7.23-7.23c.45-.45.67-1.04.67-1.63V4.8c0-1.54-1.26-2.8-2.8-2.8h-6.47zm.38 3.81c1.14 0 2.06.93 2.06 2.06 0 1.14-.93 2.06-2.06 2.06-1.14 0-2.06-.93-2.06-2.06 0-1.14.93-2.06 2.06-2.06z" />
                    </svg>
                  </div>
                  <div>
                    <p className="font-medium text-foreground">Jira</p>
                    <p className="text-sm text-muted-foreground">acme.atlassian.net</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="h-5 w-5 text-success" />
                  <Button variant="outline" size="sm">
                    Disconnect
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-lg">Notifications</CardTitle>
              <CardDescription>Configure how you receive updates</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Email Notifications</Label>
                  <p className="text-sm text-muted-foreground">
                    Receive email alerts when issues are created or errors occur
                  </p>
                </div>
                <Switch checked={emailNotifications} onCheckedChange={setEmailNotifications} />
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-lg">Processing</CardTitle>
              <CardDescription>Configure how emails are processed</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Auto-retry Failed Actions</Label>
                  <p className="text-sm text-muted-foreground">
                    Automatically retry failed issue creation after 5 minutes
                  </p>
                </div>
                <Switch checked={autoRetry} onCheckedChange={setAutoRetry} />
              </div>
            </CardContent>
          </Card>

          <Card className="border-border border-destructive/20 bg-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg text-destructive">
                <AlertTriangle className="h-5 w-5" />
                Danger Zone
              </CardTitle>
              <CardDescription>Irreversible actions</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <p className="font-medium text-foreground">Delete All Rules</p>
                  <p className="text-sm text-muted-foreground">
                    Remove all automation rules permanently
                  </p>
                </div>
                <Button variant="destructive" size="sm">
                  Delete All
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppLayout>
  )
}
