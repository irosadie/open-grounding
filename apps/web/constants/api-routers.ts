export const apiRouters = {
  health: {
    check: "/health",
  },
  auth: {
    login: "/auth/login",
    register: "/auth/register",
    logout: "/auth/logout",
    me: "/auth/me",
    tenantContext: "/auth/tenant/context",
  },
  system: {
    ready: "/ready",
    health: "/health",
  },
  rag: {
    knowledgeBases: {
      list: "/rag/knowledge-bases",
      create: "/rag/knowledge-bases",
      delete: "/rag/knowledge-bases/:id",
    },
    modelProfiles: {
      list: "/rag/model-profiles",
      create: "/rag/model-profiles",
      delete: "/rag/model-profiles/:id",
    },
    indexProfiles: {
      list: "/rag/index-profiles",
      create: "/rag/index-profiles",
      activate: "/rag/index-profiles/:id/activate",
    },
    providerCredentials: {
      list: "/rag/provider-credentials",
      set: "/rag/provider-credentials",
      revoke: "/rag/provider-credentials/:provider/:keyName",
    },
    ingestion: {
      intake: "/rag/ingestion/intake",
      complete: "/rag/ingestion/complete",
      status: "/rag/ingestion/status/:documentVersionId",
      delete: "/rag/ingestion/:documentVersionId",
    },
    query: {
      ask: "/rag/query",
      trace: "/rag/query/traces/:traceId",
      feedback: "/rag/query/traces/:traceId/feedback",
    },
  },
}
