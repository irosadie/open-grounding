import { authConfig } from "$/configs/auth"
import { serverAuthConfig } from "$/configs/auth-server"
import type { AuthTokensResponse } from "@open-grounding/types"
import axios from "axios"
import { encode, getToken } from "next-auth/jwt"
import type { NextRequest } from "next/server"
import { NextResponse } from "next/server"

const methodsWithBody = new Set(["POST", "PUT", "PATCH", "DELETE"])

type SessionToken = {
  accessToken?: string
  refreshToken?: string
  accessTokenExpires?: number
  [key: string]: unknown
}

type ProxyPayload<T> = T | { data: T }

const setSessionCookie = async (
  response: NextResponse,
  token: SessionToken,
  tokens: AuthTokensResponse,
) => {
  const encodedToken = await encode({
    token: {
      ...token,
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      accessTokenExpires: Date.now() + tokens.expiresIn * 1000,
    },
    secret: serverAuthConfig.secret,
    maxAge: authConfig.sessionMaxAgeSeconds,
  })

  response.cookies.set(serverAuthConfig.sessionCookieName, encodedToken, {
    httpOnly: true,
    sameSite: "lax",
    secure: serverAuthConfig.secureCookies,
    path: "/",
    maxAge: authConfig.sessionMaxAgeSeconds,
  })
}

const unwrapData = <T>(payload: ProxyPayload<T>): T => {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "data" in payload &&
    (payload as { data: unknown }).data
  ) {
    return (payload as { data: T }).data
  }
  return payload as T
}

const getTargetUrl = (path: string, search: string) => {
  const targetUrl = new URL(path, `${serverAuthConfig.backendApiBaseUrl}/`)
  targetUrl.search = search
  return targetUrl.toString()
}

const readBody = async (request: NextRequest) => {
  if (!methodsWithBody.has(request.method)) {
    return undefined
  }
  const textBody = await request.text()
  return textBody || undefined
}

const ensureValidStream = (
  body: ReadableStream<Uint8Array> | null,
): ReadableStream<Uint8Array> => {
  if (body) {
    return body
  }
  return new ReadableStream({
    start(controller) {
      controller.close()
    },
  })
}

// BUG-WEB-07: refresh access token the same way proxy/route.ts does so that
// an expired token does not cause a silent 401 on the stream endpoint.
const refreshAccessToken = async (
  refreshToken: string,
): Promise<AuthTokensResponse | null> => {
  try {
    const targetUrl = new URL(
      authConfig.backendRefreshPath.replace(/^\//, ""),
      `${serverAuthConfig.backendApiBaseUrl}/`,
    )
    const { data } = await axios.post<ProxyPayload<AuthTokensResponse>>(
      targetUrl.toString(),
      undefined,
      { headers: { Authorization: `Bearer ${refreshToken}` } },
    )
    return unwrapData(data)
  } catch {
    return null
  }
}

type RouteContext = {
  params: Promise<{ path: string[] }>
}

export async function POST(request: NextRequest, context: RouteContext) {
  const { path } = await context.params
  const normalizedPath = path.join("/")
  const token = (await getToken({
    req: request,
    secret: serverAuthConfig.secret,
    secureCookie: serverAuthConfig.secureCookies,
  })) as SessionToken | null

  const targetUrl = getTargetUrl(normalizedPath, request.nextUrl.search)
  const body = await readBody(request)

  // Proactively refresh if token is within 60 s of expiry (mirrors proxy/route.ts).
  let accessToken = token?.accessToken
  let refreshedTokens: AuthTokensResponse | null = null
  if (
    token?.refreshToken &&
    token.accessTokenExpires &&
    Date.now() >= token.accessTokenExpires - 60_000
  ) {
    refreshedTokens = await refreshAccessToken(token.refreshToken)
    if (refreshedTokens) {
      accessToken = refreshedTokens.accessToken
    }
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  }
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`
  }

  const upstream = await fetch(targetUrl, {
    method: request.method,
    headers,
    body,
  })

  if (
    upstream.body &&
    upstream.headers.get("content-type")?.includes("text/event-stream")
  ) {
    const response = new NextResponse(ensureValidStream(upstream.body), {
      status: upstream.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    })

    if (token && refreshedTokens) {
      await setSessionCookie(response, token, refreshedTokens)
    }

    return response
  }

  const contentType = upstream.headers.get("content-type") ?? "application/json"
  const text = await upstream.text()
  const response = new NextResponse(text, {
    status: upstream.status,
    headers: { "Content-Type": contentType },
  })

  if (token && refreshedTokens) {
    await setSessionCookie(response, token, refreshedTokens)
  }

  return response
}

export const runtime = "nodejs"
