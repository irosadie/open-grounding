import { authConfig } from "$/configs/auth"
import { serverAuthConfig } from "$/configs/auth-server"
import { getToken } from "next-auth/jwt"
import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

const CONSOLE_PREFIX = "/console"

const isProtectedRoute = (pathname: string) =>
  pathname === CONSOLE_PREFIX || pathname.startsWith(`${CONSOLE_PREFIX}/`)

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const token = await getToken({
    req: request,
    secret: serverAuthConfig.secret,
    secureCookie: serverAuthConfig.secureCookies,
  })

  const isConsoleRoute = isProtectedRoute(pathname)
  const isLoginPage = pathname === authConfig.loginPath
  const callbackUrl =
    pathname.startsWith("/") && pathname !== authConfig.loginPath
      ? pathname
      : CONSOLE_PREFIX

  if (isConsoleRoute && !token) {
    const loginUrl = new URL(authConfig.loginPath, request.url)

    loginUrl.searchParams.set("callbackUrl", callbackUrl)

    return NextResponse.redirect(loginUrl)
  }

  if (isLoginPage && token) {
    return NextResponse.redirect(new URL(CONSOLE_PREFIX, request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/console/:path*", "/login"],
}
