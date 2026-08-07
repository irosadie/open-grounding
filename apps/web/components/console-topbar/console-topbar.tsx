"use client"

import { UserMenu } from "$/components/user-menu"
import { consoleNavItems } from "$/configs/console"
import { Database, Menu } from "lucide-react"
import { usePathname } from "next/navigation"

type ConsoleTopbarProps = {
  onMenuClick?: () => void
}

export function ConsoleTopbar({ onMenuClick }: ConsoleTopbarProps) {
  const pathname = usePathname()

  const currentNav = consoleNavItems.find((item) =>
    item.href === "/console"
      ? pathname === item.href
      : pathname.startsWith(item.href),
  )

  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 md:hidden"
          aria-label="Buka menu"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-primary-500" />
          <span className="text-sm font-semibold text-gray-900">
            Open Grounding Console
          </span>
        </div>
        {currentNav && (
          <>
            <span className="hidden text-gray-300 md:block">/</span>
            <span className="hidden text-sm text-gray-500 md:block">
              {currentNav.label}
            </span>
          </>
        )}
      </div>
      <UserMenu collapsed dropdownPosition="bottom" />
    </header>
  )
}

export default ConsoleTopbar
