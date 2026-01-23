export interface Rule {
  id: string
  name: string
  trigger: {
    type: "label" | "sender" | "keyword"
    value: string
  }
  target: {
    project: string
    issueType: string
  }
  status: "active" | "paused"
  createdAt: string
  behavior: "auto-create" | "create-draft" | "manual-review"
}

export interface LogEntry {
  id: string
  emailSubject: string
  emailSender: string
  ruleId: string
  ruleName: string
  status: "success" | "failed" | "pending"
  timestamp: string
  jiraIssueKey?: string
  error?: string
}

export interface JiraProject {
  id: string
  name: string
  key: string
}

export interface JiraIssueType {
  id: string
  name: string
}

export const mockRules: Rule[] = [
  {
    id: "rule-1",
    name: "Support Tickets",
    trigger: { type: "label", value: "Support" },
    target: { project: "SUPPORT", issueType: "Bug" },
    status: "active",
    createdAt: "2024-01-15T10:30:00Z",
    behavior: "auto-create",
  },
  {
    id: "rule-2",
    name: "Feature Requests",
    trigger: { type: "sender", value: "@enterprise.com" },
    target: { project: "PRODUCT", issueType: "Story" },
    status: "active",
    createdAt: "2024-01-10T14:20:00Z",
    behavior: "create-draft",
  },
  {
    id: "rule-3",
    name: "Bug Reports",
    trigger: { type: "keyword", value: "bug report" },
    target: { project: "ENGINEERING", issueType: "Bug" },
    status: "paused",
    createdAt: "2024-01-05T09:15:00Z",
    behavior: "manual-review",
  },
]

export const mockLogs: LogEntry[] = [
  {
    id: "log-1",
    emailSubject: "Re: Login issues on production",
    emailSender: "customer@example.com",
    ruleId: "rule-1",
    ruleName: "Support Tickets",
    status: "success",
    timestamp: "2024-01-20T15:45:00Z",
    jiraIssueKey: "SUPPORT-142",
  },
  {
    id: "log-2",
    emailSubject: "Feature request: Dark mode",
    emailSender: "partner@enterprise.com",
    ruleId: "rule-2",
    ruleName: "Feature Requests",
    status: "success",
    timestamp: "2024-01-20T14:30:00Z",
    jiraIssueKey: "PRODUCT-89",
  },
  {
    id: "log-3",
    emailSubject: "Critical bug in checkout flow",
    emailSender: "urgent@customer.com",
    ruleId: "rule-3",
    ruleName: "Bug Reports",
    status: "failed",
    timestamp: "2024-01-20T12:15:00Z",
    error: "Jira API rate limit exceeded",
  },
  {
    id: "log-4",
    emailSubject: "API documentation feedback",
    emailSender: "dev@enterprise.com",
    ruleId: "rule-2",
    ruleName: "Feature Requests",
    status: "pending",
    timestamp: "2024-01-20T11:00:00Z",
  },
  {
    id: "log-5",
    emailSubject: "Password reset not working",
    emailSender: "user@example.com",
    ruleId: "rule-1",
    ruleName: "Support Tickets",
    status: "success",
    timestamp: "2024-01-19T16:20:00Z",
    jiraIssueKey: "SUPPORT-141",
  },
]

export const mockProjects: JiraProject[] = [
  { id: "proj-1", name: "Support", key: "SUPPORT" },
  { id: "proj-2", name: "Product", key: "PRODUCT" },
  { id: "proj-3", name: "Engineering", key: "ENGINEERING" },
]

export const mockIssueTypes: JiraIssueType[] = [
  { id: "type-1", name: "Bug" },
  { id: "type-2", name: "Story" },
  { id: "type-3", name: "Task" },
  { id: "type-4", name: "Epic" },
]

export const mockEmail = {
  id: "email-1",
  subject: "Re: Login issues on production",
  sender: "customer@example.com",
  senderName: "John Customer",
  body: `Hi Support Team,

We're experiencing intermittent login issues on the production environment. Multiple users have reported being unable to access their accounts since yesterday morning.

Steps to reproduce:
1. Navigate to login page
2. Enter valid credentials
3. Click "Sign In"
4. Error message: "Authentication failed"

This is affecting approximately 50 users. Please treat this as high priority.

Best regards,
John`,
  receivedAt: "2024-01-20T15:30:00Z",
  labels: ["Support", "Urgent"],
}
