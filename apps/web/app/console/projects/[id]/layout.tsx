import type { ReactNode } from "react"
import ProjectDetailLayoutContent from "./project-detail-layout-content"

export default async function ProjectDetailLayout({
  children,
  params,
}: { children: ReactNode; params: Promise<{ id: string }> }) {
  const { id } = await params
  return (
    <ProjectDetailLayoutContent projectId={id}>
      {children}
    </ProjectDetailLayoutContent>
  )
}
