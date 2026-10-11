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
  page: number,
  pageSize: number,
): Promise<DocumentVersionItem[]> => {
  const result = await axios<DocumentVersionItem[]>({
    method: "GET",
    url: apiRouters.rag.ingestion.documents,
    // Backend yang belum mendukung page/page_size boleh mengabaikan
    // params ini; UI tetap merender array penuh + windowing client-side.
    params: { knowledge_base_id: knowledgeBaseId, page, page_size: pageSize },
  })
  return result
}

export const useRagDocuments = (
  knowledgeBaseId: string | null,
  page = 1,
  pageSize = 50,
) => {
  return useQuery({
    queryKey: [
      queryKeys.rag.ingestion.documents,
      knowledgeBaseId,
      page,
      pageSize,
    ],
    queryFn: () => fetchDocuments(knowledgeBaseId as string, page, pageSize),
    enabled: !!knowledgeBaseId,
  })
}

export default useRagDocuments
