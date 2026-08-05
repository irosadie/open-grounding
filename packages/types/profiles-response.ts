export type ModelProfileResponseProps = {
  id: string
  tenantId: string
  name: string
  profileKind: string
  provider: string
  model: string
  modality: string
  dimensions: number | null
  version: string
  isActive: boolean
  createdAt: string
}

export type ModelProfileListResponse = ModelProfileResponseProps[]

export type ModelProfileCreateResponse = ModelProfileResponseProps

export type IndexProfileResponseProps = {
  id: string
  tenantId: string
  name: string
  collection: string
  dimensions: number
  distanceMetric: string
  chunkingStrategy: string
  chunkSizeTokens: number
  embeddingProfileId: string
  isActive: boolean
  createdAt: string
}

export type IndexProfileListResponse = IndexProfileResponseProps[]

export type IndexProfileCreateResponse = IndexProfileResponseProps

export type IndexProfileActivateResponse = {
  id: string
  isActive: boolean
}
