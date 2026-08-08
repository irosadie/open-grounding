"use client"

import { useKnowledgeBase } from "$/hooks/transactions/use-knowledge-bases"
import { cn } from "$/utils/cn"
import Link from "next/link"
import { usePathname } from "next/navigation"
import type { ReactNode } from "react"

type Props = {
  knowledgeBaseId: string
  children: ReactNode
}

const TABS = [
  {
    label: "Planner",
    href: (id: string) => `/console/knowledge-bases/${id}/planner`,
  },
  {
    label: "Memory",
    href: (id: string) => `/console/knowledge-bases/${id}/memory`,
  },
  {
    label: "Decomposition",
    href: (id: string) => `/console/knowledge-bases/${id}/decomposition`,
  },
  {
    label: "Ingestion Settings",
    href: (id: string) => `/console/knowledge-bases/${id}/ingestion`,
  },
]

export default function KbDetailLayoutContent({
  knowledgeBaseId,
  children,
}: Props) {
  const pathname = usePathname()
  const { data: kb, isLoading } = useKnowledgeBase(knowledgeBaseId)

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold text-gray-900">
            {isLoading ? (
              <span className="inline-block h-5 w-48 animate-pulse rounded bg-gray-200" />
            ) : (
              (kb?.name ?? "Knowledge Base")
            )}
          </h1>
          {kb ? (
            <p className="mt-0.5 text-xs text-gray-500 font-mono">{kb.slug}</p>
          ) : null}
        </div>
        {kb ? (
          <span
            className={cn(
              "shrink-0 rounded-full px-2 py-0.5 text-xs font-medium",
              kb.status === "ACTIVE"
                ? "bg-success-100 text-success-700"
                : "bg-gray-100 text-gray-500",
            )}
          >
            {kb.status === "ACTIVE" ? "Active" : kb.status}
          </span>
        ) : null}
      </div>

      {/* Tab bar */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6">
          {TABS.map((tab) => {
            const href = tab.href(knowledgeBaseId)
            const isActive =
              pathname === href || pathname.startsWith(`${href}/`)
            return (
              <Link
                key={tab.label}
                href={href}
                className={cn(
                  "whitespace-nowrap border-b-2 pb-3 text-sm font-medium transition-colors",
                  isActive
                    ? "border-primary-600 text-primary-600"
                    : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
                )}
              >
                {tab.label}
              </Link>
            )
          })}
        </nav>
      </div>

      {/* Tab content */}
      {children}
    </div>
  )
}
