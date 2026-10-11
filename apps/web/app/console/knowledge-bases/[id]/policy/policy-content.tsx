"use client"

import { Button } from "$/components/button"
import { PanelCard } from "$/components/panel-card"
import {
  type AnswerBehaviorInput,
  type GuardrailInput,
  useAnswerBehavior,
  useAnswerPolicyDefaults,
  useDeleteAnswerBehavior,
  useDeleteGuardrails,
  useDeleteProjectAnswerBehavior,
  useDeleteProjectGuardrails,
  useEffectiveAnswerPolicy,
  useGuardrails,
  useProjectAnswerBehavior,
  useProjectAnswerPolicyDefaults,
  useProjectEffectiveAnswerPolicy,
  useProjectGuardrails,
  useSaveAnswerBehavior,
  useSaveGuardrails,
  useSaveProjectAnswerBehavior,
  useSaveProjectGuardrails,
} from "$/hooks/transactions/use-answer-policy"
import {
  answerBehaviorConfigSchema,
  guardrailConfigSchema,
} from "@open-grounding/schemas"
import { Save, ShieldCheck, Trash2 } from "lucide-react"
import { useSession } from "next-auth/react"
import { useEffect, useMemo, useState } from "react"

type Props = { knowledgeBaseId?: string; projectId?: string }

const fieldClass = "rounded-lg border border-gray-300 px-3 py-2 text-sm"

export default function AnswerPolicyContent({
  knowledgeBaseId,
  projectId,
}: Props) {
  const { data: session } = useSession()
  const isAdmin =
    (session?.user as { role?: string } | undefined)?.role === "ADMIN"
  const kbAnswer = useAnswerBehavior(knowledgeBaseId ?? null)
  const projectAnswer = useProjectAnswerBehavior(projectId ?? null)
  const kbGuardrails = useGuardrails(knowledgeBaseId ?? null)
  const projectGuardrails = useProjectGuardrails(projectId ?? null)
  const kbDefaults = useAnswerPolicyDefaults(knowledgeBaseId ?? null)
  const projectDefaults = useProjectAnswerPolicyDefaults(projectId ?? null)
  const kbEffective = useEffectiveAnswerPolicy(knowledgeBaseId ?? null)
  const projectEffective = useProjectEffectiveAnswerPolicy(projectId ?? null)
  const localAnswer = projectId ? projectAnswer : kbAnswer
  const localGuardrails = projectId ? projectGuardrails : kbGuardrails
  const defaults = projectId ? projectDefaults : kbDefaults
  const effective = projectId ? projectEffective : kbEffective
  const saveKbAnswer = useSaveAnswerBehavior(knowledgeBaseId ?? "")
  const saveProjectAnswer = useSaveProjectAnswerBehavior(projectId ?? "")
  const saveKbGuardrails = useSaveGuardrails(knowledgeBaseId ?? "")
  const saveProjectGuardrails = useSaveProjectGuardrails(projectId ?? "")
  const deleteKbAnswer = useDeleteAnswerBehavior(knowledgeBaseId ?? "")
  const deleteProjectAnswer = useDeleteProjectAnswerBehavior(projectId ?? "")
  const deleteKbGuardrails = useDeleteGuardrails(knowledgeBaseId ?? "")
  const deleteProjectGuardrails = useDeleteProjectGuardrails(projectId ?? "")
  const saveAnswer = projectId ? saveProjectAnswer : saveKbAnswer
  const saveGuardrails = projectId ? saveProjectGuardrails : saveKbGuardrails
  const deleteAnswer = projectId ? deleteProjectAnswer : deleteKbAnswer
  const deleteGuardrails = projectId
    ? deleteProjectGuardrails
    : deleteKbGuardrails
  const answer =
    localAnswer.data ??
    effective.data?.answerBehavior ??
    defaults.data?.answerBehavior
  const guardrail =
    localGuardrails.data ??
    effective.data?.guardrails ??
    defaults.data?.guardrails
  const [answerForm, setAnswerForm] = useState<AnswerBehaviorInput | null>(null)
  const [guardrailForm, setGuardrailForm] = useState<GuardrailInput | null>(
    null,
  )
  const [error, setError] = useState("")
  const [saved, setSaved] = useState("")

  useEffect(() => {
    if (!answer) return
    setAnswerForm({
      version: answer.id ? `${answer.version}-next` : `${answer.version}-kb`,
      persona: answer.persona,
      responseStyle: answer.responseStyle,
      maxOutputTokens: answer.maxOutputTokens,
      sourcePolicy: answer.sourcePolicy,
      greetingPolicy: answer.greetingPolicy,
      noEvidenceAction: answer.noEvidenceAction,
      requireCitations: answer.requireCitations,
      allowMcpSources: answer.allowMcpSources,
    })
  }, [answer])

  useEffect(() => {
    if (!guardrail) return
    setGuardrailForm({
      version: guardrail.id
        ? `${guardrail.version}-next`
        : `${guardrail.version}-kb`,
      inputRules: guardrail.inputRules,
      toolRules: guardrail.toolRules,
      outputRules: guardrail.outputRules,
      maxToolCalls: guardrail.maxToolCalls,
      maxToolTimeoutSeconds: guardrail.maxToolTimeoutSeconds,
      maxToolPayloadBytes: guardrail.maxToolPayloadBytes,
      maxMcpFreshnessSeconds: guardrail.maxMcpFreshnessSeconds,
      requireToolConfirmation: guardrail.requireToolConfirmation,
    })
  }, [guardrail])

  const busy =
    saveAnswer.isPending ||
    saveGuardrails.isPending ||
    deleteAnswer.isPending ||
    deleteGuardrails.isPending
  const inheritedAnswer = !localAnswer.data
  const inheritedGuardrails = !localGuardrails.data
  const answerDisabled = !isAdmin || busy || !answerForm
  const guardrailsDisabled = !isAdmin || busy || !guardrailForm
  const sourceDescription = useMemo(() => {
    if (answerForm?.sourcePolicy === "DOCUMENT_ONLY")
      return "Hanya dokumen terpilih dan terotorisasi."
    if (answerForm?.sourcePolicy === "DOCUMENT_OR_MCP")
      return "Dokumen atau MCP yang tervalidasi; pengetahuan umum dilarang."
    return "Dokumen/MCP diprioritaskan; jawaban umum boleh bila sumber tidak tersedia."
  }, [answerForm?.sourcePolicy])

  const save = async () => {
    setError("")
    setSaved("")
    if (!answerForm || !guardrailForm) return
    const answerParsed = answerBehaviorConfigSchema.safeParse(answerForm)
    const guardrailParsed = guardrailConfigSchema.safeParse(guardrailForm)
    if (!answerParsed.success || !guardrailParsed.success) {
      setError(
        answerParsed.error?.issues[0]?.message ??
          guardrailParsed.error?.issues[0]?.message ??
          "Pengaturan tidak valid.",
      )
      return
    }
    try {
      await saveAnswer.mutateAsync(answerForm)
      await saveGuardrails.mutateAsync(guardrailForm)
      setSaved("Policy tersimpan dan akan berlaku pada query berikutnya.")
    } catch {
      setError(
        "Policy tidak dapat disimpan. Periksa hak akses dan nilai pengaturan.",
      )
    }
  }

  if (!answerForm || !guardrailForm || !answer || !guardrail)
    return <p className="text-sm text-gray-400">Memuat effective policy...</p>

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">
          Answer Policy & Guardrails
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Atur persona, sumber jawaban, batas output, dan kontrol tool untuk
          {projectId
            ? " Project ini dan seluruh Knowledge Base anggotanya."
            : " knowledge base ini."}
        </p>
      </div>

      <PanelCard
        title="Effective policy"
        description="Nilai yang benar-benar digunakan query. Nilai inherited berasal dari deployment default."
        action={<ShieldCheck className="h-5 w-5 text-primary-600" />}
      >
        <div className="grid gap-3 text-sm sm:grid-cols-2">
          <p>
            <span className="text-gray-500">Answer version:</span>{" "}
            <strong>
              {effective.data?.answerBehaviorVersion ?? answer.version}
            </strong>
          </p>
          <p>
            <span className="text-gray-500">Guardrail version:</span>{" "}
            <strong>
              {effective.data?.guardrailVersion ?? guardrail.version}
            </strong>
          </p>
          <p>
            <span className="text-gray-500">Source:</span>{" "}
            <strong>{answer.sourcePolicy}</strong>
          </p>
          <p>
            <span className="text-gray-500">Output budget:</span>{" "}
            <strong>{answer.maxOutputTokens.toLocaleString()} tokens</strong>
          </p>
        </div>
        {!isAdmin ? (
          <p className="mt-4 rounded-lg bg-gray-50 p-3 text-sm text-gray-600">
            Akun ini hanya dapat melihat effective policy. Perubahan membutuhkan
            ADMIN.
          </p>
        ) : null}
      </PanelCard>

      <PanelCard
        title="Answer behavior"
        description={
          inheritedAnswer
            ? `Inherited dari deployment default; menyimpan akan membuat override ${projectId ? "Project" : "lokal"}.`
            : `${projectId ? "Override Project" : "Override knowledge base"} aktif.`
        }
      >
        <div className="grid gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
            Version
            <input
              className={fieldClass}
              value={answerForm.version}
              onChange={(e) =>
                setAnswerForm({ ...answerForm, version: e.target.value })
              }
              disabled={answerDisabled}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
            Persona (maks. 2.000 karakter)
            <textarea
              className={fieldClass}
              rows={3}
              value={answerForm.persona}
              onChange={(e) =>
                setAnswerForm({ ...answerForm, persona: e.target.value })
              }
              disabled={answerDisabled}
              placeholder="Gaya bahasa yang aman dan tidak mengubah policy."
            />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
              Response style
              <select
                className={fieldClass}
                value={answerForm.responseStyle}
                onChange={(e) =>
                  setAnswerForm({
                    ...answerForm,
                    responseStyle: e.target
                      .value as AnswerBehaviorInput["responseStyle"],
                  })
                }
                disabled={answerDisabled}
              >
                <option value="CONCISE">Concise</option>
                <option value="BALANCED">Balanced</option>
                <option value="DETAILED">Detailed</option>
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
              Max output tokens
              <input
                className={fieldClass}
                type="number"
                min={128}
                max={8192}
                value={answerForm.maxOutputTokens}
                onChange={(e) =>
                  setAnswerForm({
                    ...answerForm,
                    maxOutputTokens: Number(e.target.value),
                  })
                }
                disabled={answerDisabled}
              />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
              Source policy
              <select
                className={fieldClass}
                value={answerForm.sourcePolicy}
                onChange={(e) => {
                  const sourcePolicy = e.target
                    .value as AnswerBehaviorInput["sourcePolicy"]
                  setAnswerForm({
                    ...answerForm,
                    sourcePolicy,
                    allowMcpSources: sourcePolicy !== "DOCUMENT_ONLY",
                    noEvidenceAction:
                      sourcePolicy === "DOCUMENT_MCP_GENERAL"
                        ? answerForm.noEvidenceAction
                        : "ABSTAIN",
                  })
                }}
                disabled={answerDisabled}
              >
                <option value="DOCUMENT_ONLY">Documents only</option>
                <option value="DOCUMENT_OR_MCP">Documents or MCP</option>
                <option value="DOCUMENT_MCP_GENERAL">
                  Documents, MCP, or general knowledge
                </option>
              </select>
              <span className="text-xs font-normal text-gray-500">
                {sourceDescription}
              </span>
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
              Greeting policy
              <select
                className={fieldClass}
                value={answerForm.greetingPolicy}
                onChange={(e) =>
                  setAnswerForm({
                    ...answerForm,
                    greetingPolicy: e.target
                      .value as AnswerBehaviorInput["greetingPolicy"],
                  })
                }
                disabled={answerDisabled}
              >
                <option value="ALLOW_UNGROUNDED">Allow safe ungrounded</option>
                <option value="REQUIRE_ALLOWED_SOURCE">
                  Require allowed source
                </option>
                <option value="REFUSE">Refuse</option>
              </select>
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={answerForm.requireCitations}
              onChange={(e) =>
                setAnswerForm({
                  ...answerForm,
                  requireCitations: e.target.checked,
                })
              }
              disabled={answerDisabled}
            />{" "}
            Require citations for source-supported claims
          </label>
          <div className="flex gap-3">
            <Button
              intent="primary"
              onClick={() => void save()}
              loading={saveAnswer.isPending || saveGuardrails.isPending}
              disabled={!isAdmin || busy}
              leftIcon={<Save className="h-4 w-4" />}
            >
              Save policy
            </Button>
            {localAnswer.data && isAdmin ? (
              <Button
                intent="danger"
                onClick={() => void deleteAnswer.mutateAsync()}
                disabled={busy}
                leftIcon={<Trash2 className="h-4 w-4" />}
              >
                Remove answer override
              </Button>
            ) : null}
          </div>
        </div>
      </PanelCard>

      <PanelCard
        title="Guardrails"
        description={
          inheritedGuardrails
            ? `Inherited platform baseline; ${projectId ? "Project" : "local"} values can only add restrictions.`
            : `${projectId ? "Override Project" : "Override knowledge base"} aktif; baseline restrictions tetap berlaku.`
        }
      >
        <div className="grid gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
            Version
            <input
              className={fieldClass}
              value={guardrailForm.version}
              onChange={(e) =>
                setGuardrailForm({ ...guardrailForm, version: e.target.value })
              }
              disabled={guardrailsDisabled}
            />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
              Max MCP calls
              <input
                className={fieldClass}
                type="number"
                min={1}
                max={32}
                value={guardrailForm.maxToolCalls}
                onChange={(e) =>
                  setGuardrailForm({
                    ...guardrailForm,
                    maxToolCalls: Number(e.target.value),
                  })
                }
                disabled={guardrailsDisabled}
              />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
              Tool timeout (seconds)
              <input
                className={fieldClass}
                type="number"
                min={1}
                max={120}
                value={guardrailForm.maxToolTimeoutSeconds}
                onChange={(e) =>
                  setGuardrailForm({
                    ...guardrailForm,
                    maxToolTimeoutSeconds: Number(e.target.value),
                  })
                }
                disabled={guardrailsDisabled}
              />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
              Payload limit (bytes)
              <input
                className={fieldClass}
                type="number"
                min={65536}
                max={10485760}
                value={guardrailForm.maxToolPayloadBytes}
                onChange={(e) =>
                  setGuardrailForm({
                    ...guardrailForm,
                    maxToolPayloadBytes: Number(e.target.value),
                  })
                }
                disabled={guardrailsDisabled}
              />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-gray-700">
              MCP freshness (seconds)
              <input
                className={fieldClass}
                type="number"
                min={0}
                max={86400}
                value={guardrailForm.maxMcpFreshnessSeconds}
                onChange={(e) =>
                  setGuardrailForm({
                    ...guardrailForm,
                    maxMcpFreshnessSeconds: Number(e.target.value),
                  })
                }
                disabled={guardrailsDisabled}
              />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={guardrailForm.requireToolConfirmation}
              onChange={(e) =>
                setGuardrailForm({
                  ...guardrailForm,
                  requireToolConfirmation: e.target.checked,
                })
              }
              disabled={guardrailsDisabled}
            />{" "}
            Require explicit confirmation before MCP calls
          </label>
          <div className="flex gap-3">
            {localGuardrails.data && isAdmin ? (
              <Button
                intent="danger"
                onClick={() => void deleteGuardrails.mutateAsync()}
                disabled={busy}
                leftIcon={<Trash2 className="h-4 w-4" />}
              >
                Remove guardrail override
              </Button>
            ) : null}
          </div>
        </div>
      </PanelCard>
      {error ? (
        <p className="rounded-lg bg-danger-50 p-3 text-sm text-danger-700">
          {error}
        </p>
      ) : null}
      {saved ? (
        <p className="rounded-lg bg-success-50 p-3 text-sm text-success-700">
          {saved}
        </p>
      ) : null}
    </div>
  )
}
