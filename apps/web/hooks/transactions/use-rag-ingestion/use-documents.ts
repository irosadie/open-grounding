"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import { useQuery } from "@tanstack/react-query"

export type DocumentVersionItem = {
  documentVersionId: string
  documentId: string
  title: string
  lifecycleState: string
  mimeType: string | null
  sizeBytes: number | null
  createdAt: string | null
}

const fetchDocuments = async (
  knowledgeBaseId: string,
): Promise<DocumentVersionItem[]> => {
  const result = await axios<DocumentVersionItem[]>({
    method: "GET",
    url: apiRouters.rag.ingestion.documents,
    params: { knowledge_base_id: knowledgeBaseId },
  })
  return result
}

export const useRagDocuments = (knowledgeBaseId: string | null) => {
  return useQuery({
    queryKey: [queryKeys.rag.ingestion.documents, knowledgeBaseId],
    queryFn: () => fetchDocuments(knowledgeBaseId as string),
    enabled: !!knowledgeBaseId,
  })
}

export default useRagDocuments
