import DecompositionConfigContent from "$/app/console/knowledge-bases/[id]/decomposition/decomposition-config-content"

export default async function ProjectDecompositionPage({
  params,
}: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return <DecompositionConfigContent projectId={id} />
}
