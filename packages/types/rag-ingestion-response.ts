export type IngestionIntakeResponse = {
  documentId: string
  documentVersionId: string
  uploadKey: string
  expiresIn: number
}

export type IngestionCompleteResponse = {
  documentVersionId: string
  lifecycleState: string
  enqueued: boolean
}

export type IngestionStatusResponse = {
  documentId: string
  documentVersionId: string
  lifecycleState: string
  mimeType: string
  sizeBytes: number
}

export type IngestionDeleteResponse = {
  success: boolean
}
