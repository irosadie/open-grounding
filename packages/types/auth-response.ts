export type AuthUserResponse = {
  id: string
  email: string
  name: string
  // BUG-WEB-05: companyId is never set by the backend — removed to avoid
  // misleading consumers who might rely on it always being 0.
  photo?: string | null
  role?: string | null
}

export type AuthTokensResponse = {
  accessToken: string
  refreshToken: string
  expiresIn: number
}

export type AuthLoginResponse = {
  user: AuthUserResponse
  tokens: AuthTokensResponse
}

export type AuthRegisterResponse = {
  // BUG-PKG-03: backend register endpoint only returns { user }, no tokens.
  // Tokens are obtained via a separate login call after registration.
  user: AuthUserResponse
}

export type AuthCurrentUserResponse = AuthUserResponse
