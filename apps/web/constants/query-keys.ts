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
