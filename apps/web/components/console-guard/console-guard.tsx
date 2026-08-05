"use client"

import { ConsoleSidebar } from "$/components/console-sidebar"
import { ConsoleTopbar } from "$/components/console-topbar"
import { LoadingSpinner } from "$/components/loading-spinner"
import { useConsoleGuard } from "$/hooks/utility/use-console-guard"
import { X } from "lucide-react"
import { useEffect, useState } from "react"

export function ConsoleGuard({ children }: { children: React.ReactNode }) {
  const { status } = useConsoleGuard()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Close sidebar on route change (any click that navigates)
  useEffect(() => {
    setSidebarOpen(false)
  }, [])

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={() => setSidebarOpen(false)}
          onKeyDown={(e) => e.key === "Escape" && setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile sidebar drawer */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-60 shrink-0 border-r border-gray-200 bg-white transition-transform duration-200 md:hidden ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-14 items-center justify-between border-b border-gray-200 px-4">
          <span className="text-sm font-semibold text-gray-900">Menu</span>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100"
            aria-label="Tutup menu"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <ConsoleSidebar onNavClick={() => setSidebarOpen(false)} />
      </aside>

      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-gray-200 bg-white md:block">
        <ConsoleSidebar />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <ConsoleTopbar onMenuClick={() => setSidebarOpen((v) => !v)} />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-6xl px-6 py-8">{children}</div>
        </main>
      </div>
    </div>
  )
}
