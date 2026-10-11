import LegacyProjectRedirect from "../legacy-project-redirect"

type Props = {
  params: Promise<{ id: string }>
}

export default async function MemoryConfigPage({ params }: Props) {
  const { id } = await params
  return <LegacyProjectRedirect knowledgeBaseId={id} section="memory" />
}
