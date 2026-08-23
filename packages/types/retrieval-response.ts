export type RetrievalConfigResponse = {
  indexProfileId: string
  denseWeight: number
  sparseWeight: number
  fusionK: number
  denseCandidates: number
  sparseCandidates: number
  fusedCandidates: number
  enabled: boolean
}
