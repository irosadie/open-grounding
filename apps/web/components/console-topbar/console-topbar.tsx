"use client"

import { UserMenu } from "$/components/user-menu"
import { Database } from "lucide-react"

export function ConsoleTopbar() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6">
      <div className="flex items-center gap-2">
        <Database className="h-5 w-5 text-primary-500" />
        <span className="text-sm font-semibold text-gray-900">RAG Console</span>
      </div>
      <UserMenu />
    </header>
  )
}

export default ConsoleTopbar
