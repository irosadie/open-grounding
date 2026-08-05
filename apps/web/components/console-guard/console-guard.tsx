"use client"

import { ConsoleSidebar } from "$/components/console-sidebar"
import { ConsoleTopbar } from "$/components/console-topbar"
import { LoadingSpinner } from "$/components/loading-spinner"
import { useConsoleGuard } from "$/hooks/utility/use-console-guard"

export function ConsoleGuard({ children }: { children: React.ReactNode }) {
  const { status } = useConsoleGuard()

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="hidden w-60 shrink-0 border-r border-gray-200 bg-white md:block">
        <ConsoleSidebar />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <ConsoleTopbar />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-6xl px-6 py-8">{children}</div>
        </main>
      </div>
    </div>
  )
}