"use client"

import { consoleNavItems } from "$/configs/console"
import { cn } from "$/utils/cn"
import { usePathname } from "next/navigation"

type ConsoleSidebarProps = {
  onNavClick?: () => void
}

export function ConsoleSidebar({ onNavClick }: ConsoleSidebarProps) {
  const pathname = usePathname()

  return (
    <nav
      aria-label="Console navigation"
      className="flex h-full flex-col gap-1 p-3"
    >
      {consoleNavItems.map((item) => {
        const isActive =
          item.href === "/console"
            ? pathname === item.href
            : pathname.startsWith(item.href)
        const Icon = item.icon

        return (
          <a
            key={item.href}
            href={item.href}
            aria-current={isActive ? "page" : undefined}
            onClick={onNavClick}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2",
              item.indent ? "ml-4 text-[13px]" : "",
              isActive
                ? "bg-primary-50 text-primary-700"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
            )}
          >
            <Icon className="h-4.5 w-4.5 shrink-0" />
            <span>{item.label}</span>
          </a>
        )
      })}
    </nav>
  )
}

export default ConsoleSidebar
