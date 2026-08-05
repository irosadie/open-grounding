import {
  Database,
  LayoutDashboard,
  MessageSquareText,
  Settings,
} from "lucide-react"

export type ConsoleNavItem = {
  label: string
  href: string
  icon: typeof Database
  description: string
}

export const consoleNavItems: ConsoleNavItem[] = [
  {
    label: "Overview",
    href: "/console",
    icon: LayoutDashboard,
    description: "Platform summary",
  },
  {
    label: "Ingestion",
    href: "/console/ingestion",
    icon: Database,
    description: "Upload and track documents",
  },
  {
    label: "Retrieval",
    href: "/console/retrieval",
    icon: MessageSquareText,
    description: "Ask grounded questions",
  },
  {
    label: "Settings",
    href: "/console/settings",
    icon: Settings,
    description: "Platform configuration",
  },
]
