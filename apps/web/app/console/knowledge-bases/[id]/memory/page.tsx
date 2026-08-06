import MemoryConfigContent from "./memory-config-content"

type Props = {
  params: Promise<{ id: string }>
}

export default async function MemoryConfigPage({ params }: Props) {
  const { id } = await params
  return <MemoryConfigContent knowledgeBaseId={id} />
}
