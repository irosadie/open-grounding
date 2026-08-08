import type { ReactNode } from "react"
import KbDetailLayoutContent from "./kb-detail-layout-content"

type Props = {
  children: ReactNode
  params: Promise<{ id: string }>
}

export default async function KnowledgeBaseDetailLayout({
  children,
  params,
}: Props) {
  const { id } = await params
  return (
    <KbDetailLayoutContent knowledgeBaseId={id}>
      {children}
    </KbDetailLayoutContent>
  )
}
