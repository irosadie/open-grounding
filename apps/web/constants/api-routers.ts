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
      decomposition: "/rag/knowledge-bases/:id/decomposition",
      decompositionDefaults: "/rag/knowledge-bases/:id/decomposition/defaults",
      memoryConfig: "/rag/knowledge-bases/:id/memory-config",
      memoryConfigDefaults: "/rag/knowledge-bases/:id/memory-config/defaults",
    },
    memory: {
      list: "/rag/memory",
      clear: "/rag/memory",
      deleteChunk: "/rag/memory/:chunkId",
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
      documents: "/rag/ingestion/documents",
    },
    query: {
      ask: "/rag/query",
      trace: "/rag/query/traces/:traceId",
      feedback: "/rag/query/traces/:traceId/feedback",
    },
  },
}
