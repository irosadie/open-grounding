import DecompositionConfigContent from "./decomposition-config-content"

type Props = {
  params: Promise<{ id: string }>
}

export default async function DecompositionConfigPage({ params }: Props) {
  const { id } = await params
  return <DecompositionConfigContent knowledgeBaseId={id} />
}
