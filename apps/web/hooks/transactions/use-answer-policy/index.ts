import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import type {
  AnswerBehaviorProfileResponse,
  AnswerPolicyDefaultsResponse,
  EffectiveAnswerPolicyResponse,
  GuardrailProfileResponse,
} from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

export type AnswerBehaviorInput = {
  version: string
  persona: string
  responseStyle: "CONCISE" | "BALANCED" | "DETAILED"
  maxOutputTokens: number
  sourcePolicy: "DOCUMENT_ONLY" | "DOCUMENT_OR_MCP" | "DOCUMENT_MCP_GENERAL"
  greetingPolicy: "ALLOW_UNGROUNDED" | "REQUIRE_ALLOWED_SOURCE" | "REFUSE"
  noEvidenceAction: "ABSTAIN" | "REFUSE" | "ANSWER_UNGROUNDED"
  requireCitations: boolean
  allowMcpSources: boolean
}

export type GuardrailInput = {
  version: string
  inputRules: string[]
  toolRules: string[]
  outputRules: string[]
  maxToolCalls: number
  maxToolTimeoutSeconds: number
  maxToolPayloadBytes: number
  maxMcpFreshnessSeconds: number
  requireToolConfirmation: boolean
}

const policyUrl = (template: string, id: string) =>
  pathVariable(template, { id })

export const useAnswerBehavior = (knowledgeBaseId: string | null) =>
  useQuery<AnswerBehaviorProfileResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.knowledgeBases.answerBehavior, knowledgeBaseId],
    queryFn: () =>
      axios({
        method: "GET",
        url: policyUrl(
          apiRouters.rag.knowledgeBases.answerBehavior,
          knowledgeBaseId as string,
        ),
      }),
    enabled: !!knowledgeBaseId,
    retry: false,
  })

export const useAnswerPolicyDefaults = (knowledgeBaseId: string | null) =>
  useQuery<AnswerPolicyDefaultsResponse, ErrorResponse<AxiosError>>({
    queryKey: [
      queryKeys.rag.knowledgeBases.answerBehaviorDefaults,
      knowledgeBaseId,
    ],
    queryFn: () =>
      axios({
        method: "GET",
        url: policyUrl(
          apiRouters.rag.knowledgeBases.answerBehaviorDefaults,
          knowledgeBaseId as string,
        ),
      }),
    enabled: !!knowledgeBaseId,
  })

export const useGuardrails = (knowledgeBaseId: string | null) =>
  useQuery<GuardrailProfileResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.knowledgeBases.guardrails, knowledgeBaseId],
    queryFn: () =>
      axios({
        method: "GET",
        url: policyUrl(
          apiRouters.rag.knowledgeBases.guardrails,
          knowledgeBaseId as string,
        ),
      }),
    enabled: !!knowledgeBaseId,
    retry: false,
  })

export const useEffectiveAnswerPolicy = (knowledgeBaseId: string | null) =>
  useQuery<EffectiveAnswerPolicyResponse, ErrorResponse<AxiosError>>({
    queryKey: [
      queryKeys.rag.knowledgeBases.effectiveAnswerPolicy,
      knowledgeBaseId,
    ],
    queryFn: () =>
      axios({
        method: "GET",
        url: policyUrl(
          apiRouters.rag.knowledgeBases.effectiveAnswerPolicy,
          knowledgeBaseId as string,
        ),
      }),
    enabled: !!knowledgeBaseId,
  })

export const useSaveAnswerBehavior = (knowledgeBaseId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    AnswerBehaviorProfileResponse,
    ErrorResponse<AxiosError>,
    AnswerBehaviorInput
  >({
    mutationKey: [queryKeys.rag.knowledgeBases.answerBehavior, knowledgeBaseId],
    mutationFn: (data) =>
      axios({
        method: "POST",
        url: policyUrl(
          apiRouters.rag.knowledgeBases.answerBehavior,
          knowledgeBaseId,
        ),
        data: {
          version: data.version,
          persona: data.persona,
          response_style: data.responseStyle,
          max_output_tokens: data.maxOutputTokens,
          source_policy: data.sourcePolicy,
          greeting_policy: data.greetingPolicy,
          no_evidence_action: data.noEvidenceAction,
          require_citations: data.requireCitations,
          allow_mcp_sources: data.allowMcpSources,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [
          queryKeys.rag.knowledgeBases.answerBehavior,
          knowledgeBaseId,
        ],
      })
      void queryClient.invalidateQueries({
        queryKey: [
          queryKeys.rag.knowledgeBases.effectiveAnswerPolicy,
          knowledgeBaseId,
        ],
      })
    },
  })
}

export const useSaveGuardrails = (knowledgeBaseId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    GuardrailProfileResponse,
    ErrorResponse<AxiosError>,
    GuardrailInput
  >({
    mutationKey: [queryKeys.rag.knowledgeBases.guardrails, knowledgeBaseId],
    mutationFn: (data) =>
      axios({
        method: "POST",
        url: policyUrl(
          apiRouters.rag.knowledgeBases.guardrails,
          knowledgeBaseId,
        ),
        data: {
          version: data.version,
          input_rules: data.inputRules,
          tool_rules: data.toolRules,
          output_rules: data.outputRules,
          max_tool_calls: data.maxToolCalls,
          max_tool_timeout_seconds: data.maxToolTimeoutSeconds,
          max_tool_payload_bytes: data.maxToolPayloadBytes,
          max_mcp_freshness_seconds: data.maxMcpFreshnessSeconds,
          require_tool_confirmation: data.requireToolConfirmation,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.knowledgeBases.guardrails, knowledgeBaseId],
      })
      void queryClient.invalidateQueries({
        queryKey: [
          queryKeys.rag.knowledgeBases.effectiveAnswerPolicy,
          knowledgeBaseId,
        ],
      })
    },
  })
}

export const useDeleteAnswerBehavior = (knowledgeBaseId: string) =>
  usePolicyDelete(
    apiRouters.rag.knowledgeBases.answerBehavior,
    queryKeys.rag.knowledgeBases.answerBehavior,
    knowledgeBaseId,
  )
export const useDeleteGuardrails = (knowledgeBaseId: string) =>
  usePolicyDelete(
    apiRouters.rag.knowledgeBases.guardrails,
    queryKeys.rag.knowledgeBases.guardrails,
    knowledgeBaseId,
  )

export const useProjectAnswerBehavior = (projectId: string | null) =>
  useQuery<AnswerBehaviorProfileResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.projects.answerBehavior, projectId],
    queryFn: () =>
      axios({
        method: "GET",
        url: policyUrl(
          apiRouters.rag.projects.answerBehavior,
          projectId as string,
        ),
      }),
    enabled: !!projectId,
    retry: false,
  })

export const useProjectAnswerPolicyDefaults = (projectId: string | null) =>
  useQuery<AnswerPolicyDefaultsResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.projects.answerBehavior, projectId, "defaults"],
    queryFn: () =>
      axios({
        method: "GET",
        url: policyUrl(
          apiRouters.rag.projects.answerBehaviorDefaults,
          projectId as string,
        ),
      }),
    enabled: !!projectId,
  })

export const useProjectGuardrails = (projectId: string | null) =>
  useQuery<GuardrailProfileResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.projects.guardrails, projectId],
    queryFn: () =>
      axios({
        method: "GET",
        url: policyUrl(apiRouters.rag.projects.guardrails, projectId as string),
      }),
    enabled: !!projectId,
    retry: false,
  })

export const useProjectEffectiveAnswerPolicy = (projectId: string | null) =>
  useQuery<EffectiveAnswerPolicyResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.projects.effectiveAnswerPolicy, projectId],
    queryFn: () =>
      axios({
        method: "GET",
        url: policyUrl(
          apiRouters.rag.projects.effectiveAnswerPolicy,
          projectId as string,
        ),
      }),
    enabled: !!projectId,
  })

export const useSaveProjectAnswerBehavior = (projectId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    AnswerBehaviorProfileResponse,
    ErrorResponse<AxiosError>,
    AnswerBehaviorInput
  >({
    mutationKey: [queryKeys.rag.projects.answerBehavior, projectId],
    mutationFn: (data) =>
      axios({
        method: "POST",
        url: policyUrl(apiRouters.rag.projects.answerBehavior, projectId),
        data: {
          version: data.version,
          persona: data.persona,
          response_style: data.responseStyle,
          max_output_tokens: data.maxOutputTokens,
          source_policy: data.sourcePolicy,
          greeting_policy: data.greetingPolicy,
          no_evidence_action: data.noEvidenceAction,
          require_citations: data.requireCitations,
          allow_mcp_sources: data.allowMcpSources,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.projects.answerBehavior, projectId],
      })
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.projects.effectiveAnswerPolicy, projectId],
      })
    },
  })
}

export const useSaveProjectGuardrails = (projectId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    GuardrailProfileResponse,
    ErrorResponse<AxiosError>,
    GuardrailInput
  >({
    mutationKey: [queryKeys.rag.projects.guardrails, projectId],
    mutationFn: (data) =>
      axios({
        method: "POST",
        url: policyUrl(apiRouters.rag.projects.guardrails, projectId),
        data: {
          version: data.version,
          input_rules: data.inputRules,
          tool_rules: data.toolRules,
          output_rules: data.outputRules,
          max_tool_calls: data.maxToolCalls,
          max_tool_timeout_seconds: data.maxToolTimeoutSeconds,
          max_tool_payload_bytes: data.maxToolPayloadBytes,
          max_mcp_freshness_seconds: data.maxMcpFreshnessSeconds,
          require_tool_confirmation: data.requireToolConfirmation,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.projects.guardrails, projectId],
      })
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.projects.effectiveAnswerPolicy, projectId],
      })
    },
  })
}

export const useDeleteProjectAnswerBehavior = (projectId: string) =>
  usePolicyDelete(
    apiRouters.rag.projects.answerBehavior,
    queryKeys.rag.projects.answerBehavior,
    projectId,
    queryKeys.rag.projects.effectiveAnswerPolicy,
  )

export const useDeleteProjectGuardrails = (projectId: string) =>
  usePolicyDelete(
    apiRouters.rag.projects.guardrails,
    queryKeys.rag.projects.guardrails,
    projectId,
    queryKeys.rag.projects.effectiveAnswerPolicy,
  )

function usePolicyDelete(
  template: string,
  key: string,
  knowledgeBaseId: string,
  effectiveKey = queryKeys.rag.knowledgeBases.effectiveAnswerPolicy,
) {
  const queryClient = useQueryClient()
  return useMutation<void, ErrorResponse<AxiosError>, void>({
    mutationKey: [key, knowledgeBaseId, "delete"],
    mutationFn: () =>
      axios({ method: "DELETE", url: policyUrl(template, knowledgeBaseId) }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [key, knowledgeBaseId] })
      void queryClient.invalidateQueries({
        queryKey: [effectiveKey, knowledgeBaseId],
      })
    },
  })
}
