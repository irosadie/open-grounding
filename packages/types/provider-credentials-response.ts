export type ProviderCredentialStatusProps = {
  provider: string
  keyName: string
  isConfigured: boolean
  updatedAt: string | null
}

export type ProviderCredentialListResponse = ProviderCredentialStatusProps[]

export type ProviderCredentialSetResponse = ProviderCredentialStatusProps

export type ProviderCredentialRevokeResponse = {
  provider: string
  keyName: string
  isConfigured: boolean
}
