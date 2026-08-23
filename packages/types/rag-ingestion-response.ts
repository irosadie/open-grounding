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

export type ParsedTextResponse = {
  versionId: string
  parsedText: string | null
  lifecycleState: string
}

export type ApproveIngestionResponse = {
  versionId: string
  lifecycleState: string
  enqueued: boolean
}

export type RejectIngestionResponse = {
  versionId: string
  lifecycleState: string
}

