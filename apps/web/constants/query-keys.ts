export const queryKeys = {
  health: {
    check: "healthCheck",
  },
  auth: {
    login: "authLogin",
    register: "authRegister",
    logout: "authLogout",
    me: "authMe",
    tenantContext: "authTenantContext",
  },
  system: {
    ready: "systemReady",
    health: "systemHealth",
  },
  rag: {
    knowledgeBases: {
      list: "ragKnowledgeBasesList",
      create: "ragKnowledgeBasesCreate",
      delete: "ragKnowledgeBasesDelete",
      decomposition: "ragKnowledgeBasesDecomposition",
      decompositionDefaults: "ragKnowledgeBasesDecompositionDefaults",
      memoryConfig: "ragKnowledgeBasesMemoryConfig",
      memoryConfigDefaults: "ragKnowledgeBasesMemoryConfigDefaults",
    },
    memory: {
      list: "ragMemoryList",
      clear: "ragMemoryClear",
      deleteChunk: "ragMemoryDeleteChunk",
    },
    modelProfiles: {
      list: "ragModelProfilesList",
      create: "ragModelProfilesCreate",
      delete: "ragModelProfilesDelete",
    },
    indexProfiles: {
      list: "ragIndexProfilesList",
      create: "ragIndexProfilesCreate",
      activate: "ragIndexProfilesActivate",
    },
    providerCredentials: {
      list: "ragProviderCredentialsList",
      set: "ragProviderCredentialsSet",
      revoke: "ragProviderCredentialsRevoke",
    },
    ingestion: {
      intake: "ragIngestionIntake",
      complete: "ragIngestionComplete",
      status: "ragIngestionStatus",
      delete: "ragIngestionDelete",
      documents: "ragIngestionDocuments",
    },
    query: {
      ask: "ragQueryAsk",
      trace: "ragQueryTrace",
      feedback: "ragQueryFeedback",
    },
  },
}
