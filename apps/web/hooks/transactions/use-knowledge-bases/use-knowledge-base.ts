"use client"

import { useKnowledgeBases } from "./use-knowledge-bases"

export const useKnowledgeBase = (id: string | null) => {
  const query = useKnowledgeBases()
  const kb = query.data?.find((k) => k.id === id) ?? null
  return { ...query, data: kb }
}
