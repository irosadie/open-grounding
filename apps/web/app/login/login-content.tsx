"use client"

import { Button } from "$/components/button"
import { Input } from "$/components/input"
import { PanelCard } from "$/components/panel-card"
import { authConfig } from "$/configs/auth"
import { type LoginProps, loginSchema } from "@open-grounding/schemas"
import { signIn, useSession } from "next-auth/react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  type FormEvent,
  useEffect,
  useMemo,
  useState,
  useTransition,
} from "react"

const sanitizeCallbackUrl = (value: string | null) => {
  if (value?.startsWith("/")) {
    return value
  }

  return authConfig.defaultRedirectPath
}

type LoginErrors = Partial<Record<keyof LoginProps, string>>

export default function LoginContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { status } = useSession()
  const [isPending, startTransition] = useTransition()
  const [formError, setFormError] = useState("")
  const [fieldErrors, setFieldErrors] = useState<LoginErrors>({})
  const sessionExpired = searchParams.get("sessionExpired") === "1"
  const urlError = searchParams.get("error")
  const [form, setForm] = useState<LoginProps>({
    email: "",
    password: "",
  })

  const callbackUrl = useMemo(
    () => sanitizeCallbackUrl(searchParams.get("callbackUrl")),
    [searchParams],
  )

  useEffect(() => {
    // BUG-WEB-04: use a cancelled flag to prevent state update after unmount
    let cancelled = false
    if (status === "authenticated" && !cancelled) {
      router.replace(callbackUrl)
    }
    return () => {
      cancelled = true
    }
  }, [callbackUrl, router, status])

  const handleChange = (field: keyof LoginProps, value: string) => {
    setForm((current) => ({
      ...current,
      [field]: value,
    }))
    setFieldErrors((current) => ({
      ...current,
      [field]: undefined,
    }))
    setFormError("")
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const parsedForm = loginSchema.safeParse(form)

    if (!parsedForm.success) {
      const nextErrors: LoginErrors = {}

      for (const issue of parsedForm.error.issues) {
        const field = issue.path[0]

        if (field === "email" || field === "password") {
          nextErrors[field] = issue.message
        }
      }

      setFieldErrors(nextErrors)
      return
    }

    startTransition(() => {
      void (async () => {
        const result = await signIn("credentials", {
          ...parsedForm.data,
          redirect: false,
          callbackUrl,
        })

        if (result?.error) {
          setFormError(
            result.error === "CredentialsSignin"
              ? "Incorrect email or password"
              : result.error,
          )
          return
        }

        router.replace(result?.url || callbackUrl)
        router.refresh()
      })()
    })
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md items-center px-6 py-12">
      <PanelCard
        className="w-full rounded-3xl"
        title="Sign In"
        description="Starter credentials flow via NextAuth and proxy BFF"
      >
        <form className="space-y-4" onSubmit={handleSubmit}>
          <Input
            autoComplete="email"
            label="Email"
            name="email"
            type="email"
            value={form.email}
            error={fieldErrors.email}
            onChange={(event) => handleChange("email", event.target.value)}
            placeholder="you@example.com"
            required
          />
          <Input
            autoComplete="current-password"
            label="Password"
            name="password"
            type="password"
            value={form.password}
            error={fieldErrors.password}
            onChange={(event) => handleChange("password", event.target.value)}
            placeholder="Enter your password"
            required
          />

          {formError ? (
            <p className="text-sm text-danger-500">{formError}</p>
          ) : urlError && urlError !== "undefined" ? (
            <p className="text-sm text-danger-500">
              Incorrect email or password
            </p>
          ) : null}

          {sessionExpired && !formError && !urlError ? (
            <p className="rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-700">
              Your session has expired. Please sign in again.
            </p>
          ) : null}

          <Button
            className="w-full justify-center"
            type="submit"
            loading={isPending}
          >
            Sign In
          </Button>

          <p className="text-center text-sm text-slate-600">
            Belum punya akun?{" "}
            <a
              href="/register"
              className="font-semibold text-primary-600 underline-offset-4 hover:underline"
            >
              Daftar di sini
            </a>
          </p>
        </form>
      </PanelCard>
    </main>
  )
}
