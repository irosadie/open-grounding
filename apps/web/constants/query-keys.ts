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
    ingestion: {
      intake: "ragIngestionIntake",
      complete: "ragIngestionComplete",
      status: "ragIngestionStatus",
      delete: "ragIngestionDelete",
    },
    query: {
      ask: "ragQueryAsk",
      trace: "ragQueryTrace",
      feedback: "ragQueryFeedback",
    },
  },
}
