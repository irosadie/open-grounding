import {
  Brain,
  Cpu,
  Database,
  KeyRound,
  LayoutDashboard,
  LayoutList,
  MessageSquareText,
  Settings,
  Upload,
  Wrench,
} from "lucide-react"

export type ConsoleNavItem = {
  label: string
  href: string
  icon: typeof Database
  description: string
  indent?: boolean
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
  },
  {
    label: "Ingestion",
    href: "/console/ingestion",
    icon: Upload,
    description: "Upload and track documents",
  },
  {
    label: "Retrieval",
    href: "/console/retrieval",
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
    label: "Settings",
    href: "/console/settings",
    icon: Settings,
    description: "Platform configuration",
  },
  {
    label: "Model Profiles",
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
    label: "Providers",
    href: "/console/settings/providers",
    icon: KeyRound,
    description: "API keys and provider credentials",
    indent: true,
  },
  {
    label: "Tools",
    href: "/console/settings/tools",
    icon: Wrench,
    description: "Live tool registry and permissions",
    indent: true,
  },
]
