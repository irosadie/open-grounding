import AnswerPolicyContent from "$/app/console/knowledge-bases/[id]/policy/policy-content"

export default async function ProjectPolicyPage({
  params,
}: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return <AnswerPolicyContent projectId={id} />
}
