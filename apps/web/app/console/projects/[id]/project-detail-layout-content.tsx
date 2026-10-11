"use client"

import { useProject } from "$/hooks/transactions/use-projects"
import { cn } from "$/utils/cn"
import Link from "next/link"
import { usePathname } from "next/navigation"
import type { ReactNode } from "react"

const tabs = [
  ["Planner", "planner"],
  ["Answer Policy", "policy"],
  ["Memory", "memory"],
  ["Decomposition", "decomposition"],
] as const

export default function ProjectDetailLayoutContent({
  projectId,
  children,
}: { projectId: string; children: ReactNode }) {
  const pathname = usePathname()
  const { data: project, isLoading } = useProject(projectId)
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">
          {isLoading ? "Project" : (project?.name ?? "Project")}
        </h1>
        <p className="mt-0.5 font-mono text-xs text-gray-500">
          {project?.slug}
        </p>
      </div>
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6 overflow-x-auto">
          {tabs.map(([label, segment]) => {
            const href = `/console/projects/${projectId}/${segment}`
            const active = pathname === href || pathname.startsWith(`${href}/`)
            return (
              <Link
                key={segment}
                href={href}
                className={cn(
                  "whitespace-nowrap border-b-2 pb-3 text-sm font-medium",
                  active
                    ? "border-primary-600 text-primary-600"
                    : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
                )}
              >
                {label}
              </Link>
            )
          })}
          <Link
            href={`/console/projects/${projectId}`}
            className={cn(
              "whitespace-nowrap border-b-2 pb-3 text-sm font-medium",
              pathname === `/console/projects/${projectId}`
                ? "border-primary-600 text-primary-600"
                : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
            )}
          >
            Knowledge Bases
          </Link>
        </nav>
      </div>
      {children}
    </div>
  )
}
