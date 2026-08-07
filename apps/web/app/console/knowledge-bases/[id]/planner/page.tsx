import PlannerConfigContent from "./planner-config-content"

type Props = {
  params: Promise<{ id: string }>
}

export default async function PlannerConfigPage({ params }: Props) {
  const { id } = await params
  return <PlannerConfigContent knowledgeBaseId={id} />
}
