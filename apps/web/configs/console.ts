import {
  Brain,
  ChartNoAxesColumnIncreasing,
  Cpu,
  Database,
  KeyRound,
  LayoutDashboard,
  LayoutList,
  MessageSquareText,
  Network,
  Settings,
  Upload,
} from "lucide-react"

export type ConsoleNavItem = {
  label: string
  href: string
  icon: typeof Database
  description: string
  indent?: boolean
  group?: string
}

export const consoleNavItems: ConsoleNavItem[] = [
  {
    label: "Overview",
    href: "/console",
    icon: LayoutDashboard,
    description: "Platform summary",
  },
  {
    label: "Knowledge Bases",
    href: "/console/knowledge-bases",
    icon: Database,
    description: "Manage knowledge bases",
    group: "WORKSPACE",
  },
  {
    label: "Documents",
    href: "/console/document",
    icon: Upload,
    description: "Upload and track documents",
  },
  {
    label: "Query",
    href: "/console/query",
    icon: MessageSquareText,
    description: "Ask grounded questions",
  },
  {
    label: "Memory",
    href: "/console/memory",
    icon: Brain,
    description: "Manage your conversation memory",
  },
  {
    label: "Configuration",
    href: "/console/settings",
    icon: Settings,
    description: "Platform configuration",
    group: "SETTINGS",
  },
  {
    label: "Models",
    href: "/console/settings/models",
    icon: Cpu,
    description: "Embedding and generation models",
    indent: true,
  },
  {
    label: "Index Profiles",
    href: "/console/settings/index-profiles",
    icon: LayoutList,
    description: "Vector index configuration",
    indent: true,
  },
  {
    label: "Confidence",
    href: "/console/settings/confidence",
    icon: ChartNoAxesColumnIncreasing,
    description: "Calibration and confidence settings",
    indent: true,
  },
  {
    label: "Providers",
    href: "/console/settings/providers",
    icon: KeyRound,
    description: "API keys and provider credentials",
    indent: true,
  },
  {
    label: "MCP Servers",
    href: "/console/settings/mcp",
    icon: Network,
    description: "Connect and manage MCP servers",
    indent: true,
  },
]
