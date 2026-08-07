"use client"

import { consoleNavItems } from "$/configs/console"
import { cn } from "$/utils/cn"
import { ChevronDown } from "lucide-react"
import { usePathname } from "next/navigation"
import { useState } from "react"

type ConsoleSidebarProps = {
  onNavClick?: () => void
}

export function ConsoleSidebar({ onNavClick }: ConsoleSidebarProps) {
  const pathname = usePathname()
  const inSettings = pathname.startsWith("/console/settings")
  const [settingsOpen, setSettingsOpen] = useState(inSettings)

  return (
    <nav
      aria-label="Console navigation"
      className="flex h-full flex-col gap-0.5 p-3"
    >
      {consoleNavItems.map((item) => {
        const isActive =
          item.href === "/console"
            ? pathname === item.href
            : pathname.startsWith(item.href)
        const Icon = item.icon
        const isSettingsParent = item.href === "/console/settings"
        const isSubItem = item.indent

        if (isSubItem && !settingsOpen) {
          return null
        }

        return (
          <div key={item.href}>
            {item.group && (
              <p className="mb-1 mt-3 px-3 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                {item.group}
              </p>
            )}
            {isSettingsParent ? (
              <button
                type="button"
                onClick={() => setSettingsOpen((prev) => !prev)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2",
                  isActive
                    ? "bg-primary-50 text-primary-700"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="flex-1 text-left">{item.label}</span>
                <ChevronDown
                  className={cn(
                    "h-3.5 w-3.5 text-gray-400 transition-transform",
                    settingsOpen ? "rotate-180" : "",
                  )}
                />
              </button>
            ) : (
              <a
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                onClick={onNavClick}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2",
                  isSubItem ? "ml-3 text-[13px]" : "",
                  isActive
                    ? "bg-primary-50 text-primary-700"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
              </a>
            )}
          </div>
        )
      })}
    </nav>
  )
}

export default ConsoleSidebar
