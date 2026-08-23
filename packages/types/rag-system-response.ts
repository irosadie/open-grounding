export type ReadinessComponent = {
  name: string
  available: boolean
  detail: string | null
}

export type ReadinessResponse = {
  status: "ready" | "degraded"
  ragEnabled: boolean
  ragRuntimeMode: string
  deploymentTenantId: string | null
  components: ReadinessComponent[]
}

export type HealthResponse = {
  status: string
  service: string
  timestamp: string
  tenant: {
    tenantId: string | null
    membershipId: string | null
    userId: string | null
    role: string | null
  }
}

export type TenantContextResponse = {
  tenantId: string
  membershipId: string
  userId: string
}
