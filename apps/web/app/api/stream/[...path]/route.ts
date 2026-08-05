import { authConfig } from "$/configs/auth"
import { serverAuthConfig } from "$/configs/auth-server"
import { getToken } from "next-auth/jwt"
import type { NextRequest } from "next/server"
import { NextResponse } from "next/server"

const methodsWithBody = new Set(["POST", "PUT", "PATCH", "DELETE"])

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
  })) as { accessToken?: string } | null

  const targetUrl = getTargetUrl(normalizedPath, request.nextUrl.search)
  const body = await readBody(request)

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  }
  if (token?.accessToken) {
    headers.Authorization = `Bearer ${token.accessToken}`
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
    return new NextResponse(ensureValidStream(upstream.body), {
      status: upstream.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    })
  }

  const contentType = upstream.headers.get("content-type") ?? "application/json"
  const text = await upstream.text()
  return new NextResponse(text, {
    status: upstream.status,
    headers: { "Content-Type": contentType },
  })
}

export const runtime = "nodejs"

export const config = {
  matcher: [`${authConfig.proxyApiBasePath}/stream/:path*`],
}
