"use client"

import { useKnowledgeBase } from "$/hooks/transactions/use-knowledge-bases"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect } from "react"

export default function LegacyProjectRedirect({
  knowledgeBaseId,
  section,
}: {
  knowledgeBaseId: string
  section: "planner" | "policy" | "memory" | "decomposition"
}) {
  const router = useRouter()
  const { data: kb, isLoading } = useKnowledgeBase(knowledgeBaseId)
  useEffect(() => {
    if (kb?.projectId)
      router.replace(`/console/projects/${kb.projectId}/${section}`)
  }, [kb?.projectId, router, section])
  if (isLoading)
    return <p className="text-sm text-gray-400">Opening Project settings...</p>
  if (kb?.projectId)
    return <p className="text-sm text-gray-400">Opening owning Project...</p>
  return (
    <p className="rounded-lg bg-warning-50 p-4 text-sm text-warning-700">
      Knowledge Base ini belum memiliki Project aktif.{" "}
      <Link className="underline" href="/console/projects">
        Buka Projects
      </Link>
      .
    </p>
  )
}
