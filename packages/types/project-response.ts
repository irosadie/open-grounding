export type ProjectKnowledgeBaseResponse = {
  id: string
  slug: string
  name: string
  status: string
  projectId: string
  createdAt: string
  updatedAt: string
}

export type ProjectResponse = {
  id: string
  tenantId: string
  slug: string
  name: string
  status: "ACTIVE" | "ARCHIVED"
  isDefault: boolean
  knowledgeBases: ProjectKnowledgeBaseResponse[]
  migrationReviews: ProjectMigrationReviewResponse[]
  createdAt: string
  updatedAt: string
}

export type ProjectMigrationReviewResponse = {
  id: string
  knowledgeBaseId: string | null
  configKind: string
  status: "OPEN" | "RESOLVED" | string
  legacyCount: number
  createdAt: string
  updatedAt: string
}

export type ProjectListResponse = ProjectResponse[]
