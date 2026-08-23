"use client"

import { authConfig } from "$/configs/auth"
import { useSession } from "next-auth/react"
import { usePathname, useRouter } from "next/navigation"
import { useEffect } from "react"

type UseConsoleGuardResult = {
  status: "loading" | "authenticated"
}

const buildLoginUrl = (pathname: string) => {
  const callbackUrl = pathname.startsWith("/")
    ? pathname
    : authConfig.defaultRedirectPath
  const params = new URLSearchParams({ callbackUrl })
  return `${authConfig.loginPath}?${params.toString()}`
}

export const useConsoleGuard = (): UseConsoleGuardResult => {
  const { status } = useSession()
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(buildLoginUrl(pathname))
    }
  }, [pathname, router, status])

  if (status === "authenticated") {
    return { status: "authenticated" }
  }

  return { status: "loading" }
}
