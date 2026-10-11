import MemoryConfigContent from "$/app/console/knowledge-bases/[id]/memory/memory-config-content"

export default async function ProjectMemoryPage({
  params,
}: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return <MemoryConfigContent projectId={id} />
}
