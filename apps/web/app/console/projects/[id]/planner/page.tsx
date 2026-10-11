import PlannerConfigContent from "$/app/console/knowledge-bases/[id]/planner/planner-config-content"

export default async function ProjectPlannerPage({
  params,
}: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return <PlannerConfigContent projectId={id} />
}
