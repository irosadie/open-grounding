import QueryProvider from "$/providers/query-provider"
import SessionProviderWrapper from "$/providers/session-provider"
import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "open-grounding",
  description: "Open Grounding — grounded retrieval platform powered by RAG",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>
        <SessionProviderWrapper>
          <QueryProvider>{children}</QueryProvider>
        </SessionProviderWrapper>
      </body>
    </html>
  )
}
