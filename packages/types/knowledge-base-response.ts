export type KnowledgeBaseResponseProps = {
  id: string
  tenantId: string
  slug: string
  name: string
  status: string
  createdAt: string
  updatedAt: string
}

export type KnowledgeBaseListResponse = KnowledgeBaseResponseProps[]

export type KnowledgeBaseCreateResponse = KnowledgeBaseResponseProps

export type KnowledgeBaseDeleteResponse = {
  id: string
  status: string
}
